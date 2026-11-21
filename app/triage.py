"""CivicResolve NEXUS local AI-assisted triage.

Model: character n-gram TF-IDF + Multinomial Naive Bayes trained on small,
handwritten example phrases. NOT a production or government-validated model.
Safety-critical escalation is deterministic and explainable.
"""
import math
import re
from difflib import SequenceMatcher
from functools import lru_cache
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline

CATEGORIES = {
    "water": ("Water & Sanitation", "Water Works"),
    "roads": ("Roads & Mobility", "Roads & Transport"),
    "waste": ("Waste Management", "Solid Waste Management"),
    "lights": ("Electricity & Lighting", "Electrical Maintenance"),
    "health": ("Public Health", "Public Health Department"),
    "spaces": ("Public Spaces", "Parks & Public Infrastructure"),
}

EXAMPLES = {
"water": [
 "Water pipe is leaking near my street", "Burst water pipeline flooding the road",
 "No drinking water supply since yesterday", "Sewage overflowing from the manhole",
 "Dirty tap water with strange smell", "Blocked drainage during heavy rainfall",
 "Open drain near school", "Broken sewer pipe beside apartment",
 "Low water pressure in houses", "Water main leakage close to hospital",
 "The public tap has stopped working", "Road filled with wastewater",
 "Toilet sewage leakage near market", "தண்ணீர் குழாய் உடைந்து தண்ணீர் வீணாகிறது",
 "குடிநீர் வரவில்லை கழிவுநீர் தெருவில் ஓடுகிறது",
 "Water tank is contaminated", "Overflowing stormwater drain",
 "Rainwater stagnating in drain", "Waterlogging on residential street",
 "Damaged water connection near bus stand",
],
"roads": [
 "Dangerous pothole on the main road", "Broken road surface causing accidents",
 "Traffic signal is not functioning", "Footpath is cracked and unsafe",
 "Bridge damaged after rain", "Road divider damaged near junction",
 "Open manhole on a busy road", "School crossing lacks zebra stripes",
 "A fallen tree is blocking the road", "Speed breaker damaged at junction",
 "Large crater causing bike accidents", "Cyclists cannot use road safely",
 "Pedestrian walkway collapsed", "சாலையில் பெரிய பள்ளம் உள்ளது",
 "போக்குவரத்து சிக்னல் வேலை செய்யவில்லை",
 "Loose pavement tiles near bus stop", "Dangerous road shoulder erosion",
 "Road markings completely faded", "Vehicles cannot pass due to broken bridge",
 "Collapsed culvert on approach road",
],
"waste": [
 "Garbage bin overflowing for three days", "Waste not collected from our street",
 "Illegal dumping of plastic trash", "Burning piles of rubbish near houses",
 "Dead animal not removed from roadside", "Public garbage disposal is overflowing",
 "Uncollected household waste", "Construction debris dumped on pavement",
 "Food waste attracts stray dogs", "Garbage truck missed the area",
 "Market street full of litter", "Trash piled around the playground",
 "குப்பை தொட்டி நிரம்பி வழிகிறது", "குப்பை வண்டி வரவில்லை",
 "Mosquitoes near accumulated garbage", "Dumping ground smells terrible",
 "Waste burning creates smoke", "Plastic waste blocking the lane",
 "Biomedical waste illegally dumped", "Public dustbin is broken",
],
"lights": [
 "Streetlight is not working at night", "Power pole sparks during rain",
 "Exposed electric wire beside school", "Street lamps broken at the park",
 "Dark alley because the light is out", "Damaged electric transformer",
 "Fallen power cable on sidewalk", "Frequent electricity outage",
 "Traffic junction street lighting failure", "Shocking exposed wiring near bus stop",
 "High voltage box is open", "Loose electrical pole leaning over road",
 "தெரு விளக்கு எரியவில்லை", "மின்கம்பி அறுந்து விழுந்துள்ளது",
 "Electric supply disruption in our block", "Transformer making a loud buzzing noise",
 "Broken lamp post on the road", "Faulty electrical connection",
 "Electric box uncovered", "Street lighting not repaired for weeks",
],
"health": [
 "Mosquito infestation and dengue risk", "Stray dogs attacking children",
 "Stagnant water causing mosquito breeding", "Unsafe public health conditions",
 "Public toilet unhygienic and broken", "Food stall selling spoiled food",
 "Possible disease outbreak in the colony", "Dead rats near clinic",
 "Unsanitary market creating infection risk", "Contaminated food sold near school",
 "Health centre lacks sanitation", "Foul smell making residents sick",
 "கொசு தொல்லை அதிகமாக உள்ளது", "சுகாதார பிரச்சனை உள்ளது",
 "Dengue cases reported in our neighbourhood", "Breathing problems from toxic fumes",
 "Open medical waste near playground", "Public toilet needs urgent cleaning",
 "Unsafe water causing diarrhoea", "Health hazard near homes",
],
"spaces": [
 "Playground equipment is damaged", "Park benches are broken",
 "Public library roof is leaking", "Community hall needs maintenance",
 "Public park gate does not close", "Trees in park need pruning",
 "Broken fence around children's playground", "Public garden irrigation broken",
 "Civic building wall has cracks", "Bus shelter bench is missing",
 "Street signs damaged in the colony", "Footbridge railing in the park is broken",
 "பூங்கா பராமரிப்பு இல்லை", "விளையாட்டு மைதானம் சேதமடைந்துள்ளது",
 "Public toilet door is broken in park", "Public sports ground needs repair",
 "Community centre is in poor condition", "Damaged notice board at park",
 "Public seat destroyed", "Public infrastructure damaged",
]}

# Domain-specific signals supplement the language model, especially for very short text.
SIGNALS = {
 "water": ("water", "pipe", "sewage", "sewer", "drain", "flood", "tap", "pipeline", "waterlogging", "தண்ணீர்", "குடிநீர்", "கழிவுநீர்"),
 "roads": ("pothole", "road", "traffic", "bridge", "footpath", "crossing", "pavement", "culvert", "சாலை", "போக்குவரத்து"),
 "waste": ("garbage", "waste", "rubbish", "trash", "dump", "litter", "dustbin", "குப்பை"),
 "lights": ("electric", "streetlight", "light pole", "power", "wire", "transformer", "voltage", "மின்கம்பி", "விளக்கு"),
 "health": ("mosquito", "dengue", "disease", "infection", "stray dog", "health", "toxic", "diarrhoea", "கொசு", "சுகாதார"),
 "spaces": ("park", "playground", "garden", "library", "community hall", "bench", "பூங்கா", "மைதானம்"),
}

DANGER_TERMS = ("electrocut", "live wire", "live electrical wire", "electric wire", "exposed wire", "downed wire", "spark", "collapsed", "collapse", "burst", "flooding", "fire", "injur", "accident", "unsafe", "toxic", "attack", "infection", "uncovered manhole", "dengue", "மின்கம்பி அறுந்து", "உடைந்து")
VULNERABLE_TERMS = ("school", "children", "hospital", "clinic", "elderly", "disabled", "bus stop", "playground", "மாணவர்கள்", "பள்ளி", "மருத்துவமனை")
URGENCY_TERMS = ("urgent", "immediate", "danger", "emergency", "today", "critical", "risk", "help", "கடுமையான", "அவசரம்")

@lru_cache(maxsize=1)
def _model():
    x, y = [], []
    for key, phrases in EXAMPLES.items():
        x.extend(phrases)
        y.extend([key] * len(phrases))
    return Pipeline([
        ("tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True)),
        ("classifier", MultinomialNB(alpha=0.12)),
    ]).fit(x, y)

def classify(text: str) -> dict:
    normalized = text.lower().strip()
    probabilities = _model().predict_proba([normalized])[0]
    classes = _model().named_steps["classifier"].classes_
    ranked = sorted(zip(classes, probabilities), key=lambda t: -t[1])
    key, confidence = ranked[0]
    # Strong domain vocabulary takes precedence when short descriptions confuse the classifier.
    scored = {k: sum(1 for term in terms if term in normalized) for k, terms in SIGNALS.items()}
    winner = max(scored, key=scored.get)
    if scored[winner] >= 2 and scored[winner] > scored.get(key, 0):
        key = winner
        confidence = max(confidence, 0.68)
    # The tool does not invent certainty for out-of-domain complaints.
    if confidence < 0.24 and max(scored.values()) == 0:
        return {"key":"other", "category":"General Civic Services", "department":"Citizen Service Centre", "confidence":round(float(confidence), 2)}
    cat, department = CATEGORIES[key]
    return {"key":key, "category":cat, "department":department, "confidence":round(float(confidence), 2)}

def score(text: str, category_key: str, reports: int = 1, age_hours: float = 0) -> dict:
    lower = text.lower()
    base = {"water":38,"roads":35,"waste":28,"lights":38,"health":42,"spaces":25,"other":25}.get(category_key,25)
    danger = any(t in lower for t in DANGER_TERMS)
    vulnerable = any(t in lower for t in VULNERABLE_TERMS)
    urgency = any(t in lower for t in URGENCY_TERMS)
    # Limited crowd weight protects small/underreported areas from being ignored.
    recurrence = min(12, 4 * max(0, reports - 1))
    ageing = min(20, int(max(0, age_hours) / 6))
    value = min(100, base + 23 * danger + 12 * vulnerable + 8 * urgency + recurrence + ageing)
    reasons = [f"Baseline service risk: +{base}"]
    if danger: reasons.append("Potential safety hazard: +23")
    if vulnerable: reasons.append("Sensitive public setting: +12")
    if urgency: reasons.append("Urgency language: +8")
    if recurrence: reasons.append(f"Corroborating reports (capped): +{recurrence}")
    if ageing: reasons.append(f"Waiting-time escalation: +{ageing}")
    reasons.append("Officer review required before public-safety decisions")
    label = "Critical" if value >= 78 else "High" if value >= 60 else "Moderate" if value >= 40 else "Routine"
    return {"score":value,"label":label,"reasons":reasons}

def similarity(text_a: str, text_b: str) -> float:
    """Token overlap plus fuzzy matching; a conservative clustering heuristic."""
    def tokens(s):
        return set(re.findall(r"[\w\u0B80-\u0BFF]+", s.lower())) - {
            "the","and","near","our","there","this","is","are","in","at","a","an","of","for","to","on","my","has","from","very"
        }
    a, b = tokens(text_a), tokens(text_b)
    jaccard = len(a & b) / len(a | b) if a | b else 0
    fuzzy = SequenceMatcher(None, text_a.lower(), text_b.lower()).ratio()
    return round(0.70 * jaccard + 0.30 * fuzzy, 3)

def analyze(text: str, reports: int = 1, age_hours: float = 0) -> dict:
    c = classify(text)
    return {**c, **score(text, c["key"], reports, age_hours)}
