"""CivicResolve NEXUS: civic intelligence demonstration API.

Public citizen reporting; authenticated officer workflows. Demo aliases are not
verified civic identities, so production deployments need full identity controls.
"""
import json
import secrets
import time
import hashlib
import hmac
from collections import defaultdict
import os
import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
from .database import Incident, Report, Event, Verification, make_session, now
from .triage import analyze, similarity, score

ROOT = Path(__file__).resolve().parent
MEDIA = Path(os.environ.get("MEDIA_DIR", str(ROOT.parent / "data" / "uploads")))
MEDIA.mkdir(parents=True, exist_ok=True)

WARD_CHOICES = ["RS Puram", "Gandhipuram", "Peelamedu", "Saibaba Colony", "Ukkadam", "Singanallur", "Saravanampatti", "Town Hall", "Other"]

class ComplaintIn(BaseModel):
    name: str = Field(min_length=2, max_length=45)
    description: str = Field(min_length=18, max_length=1600)
    ward: str = Field(min_length=2, max_length=80)
    location: str = Field(default="", max_length=150)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    @field_validator("name", "description", "ward", "location")
    @classmethod
    def strip(cls, v):
        return re.sub(r"\s+", " ", v).strip()

class PreviewIn(BaseModel):
    description: str = Field(min_length=8, max_length=1600)

class ActionIn(BaseModel):
    action: Literal["assign", "start", "request_verification"]
    actor: str = Field(min_length=2, max_length=45)
    note: str = Field(min_length=8, max_length=800)
    department: str | None = Field(default=None, max_length=90)

class VerifyIn(BaseModel):
    name: str = Field(min_length=2, max_length=45)
    verdict: Literal["confirm", "dispute"]
    note: str = Field(min_length=8, max_length=800)

class LoginIn(BaseModel):
    email: str = Field(min_length=5, max_length=100)
    password: str = Field(min_length=8, max_length=200)

class AssistantIn(BaseModel):
    message: str = Field(min_length=3, max_length=900)
    ward: str = Field(default="all", max_length=80)
    incident_id: int | None = Field(default=None, ge=1)

class SupportIn(BaseModel):
    name: str = Field(min_length=2, max_length=45)
    note: str = Field(min_length=8, max_length=600)


def dt_str(d):
    if not d:
        return None
    return d.isoformat() + ("Z" if d.tzinfo is None else "")


def event(db, incident, kind, actor, note, attachment=""):
    db.add(Event(incident_id=incident.id, kind=kind, actor=actor, note=note, attachment=attachment))


def civic_memory_reference(incident):
    """Return a verified prior incident code from an audited recurrence event, if any."""
    for entry in incident.events:
        if entry.kind == "recurrence":
            match = re.search(r"CR-(\d{4,})", entry.note)
            if match:
                return f"CR-{match.group(1)}"
    return None


def recurrence_candidate(db, payload, classified_key):
    """Flag likely repeat infrastructure problems without conflating new and resolved cases.

    A different ward, department/category, nonmatching landmark, or a repair
    verified more than 90 days ago is not enough evidence to link incidents.
    This is a transparent heuristic, not causal root-cause diagnosis.
    """
    cutoff = now() - timedelta(days=90)
    previous = db.scalars(
        select(Incident).where(
            Incident.ward == payload.ward,
            Incident.category_key == classified_key,
            Incident.status == "resolved",
            Incident.updated_at >= cutoff,
        ).order_by(Incident.updated_at.desc())
    ).all()
    for old in previous:
        if not payload.location or not old.location:
            continue  # A shared physical landmark is required to avoid false links.
        if similarity(payload.location, old.location) < 0.52:
            continue
        if similarity(payload.description, old.description) < 0.48:
            continue
        return old
    return None


def apply_memory_bonus(priority, prior_code):
    """Explain a capped recurrence review bonus without implying validated causality."""
    if not prior_code:
        return priority
    value = min(100, priority["score"] + 10)
    label = "Critical" if value >= 78 else "High" if value >= 60 else "Moderate" if value >= 40 else "Routine"
    reasons = priority["reasons"][:-1] + ["Previously verified issue may have recurred: +10 (check root cause)", priority["reasons"][-1]]
    return {"score": value, "label": label, "reasons": reasons}


def show(incident, expanded=False):
    date = incident.created_at
    if date.tzinfo is None: date = date.replace(tzinfo=timezone.utc)
    elapsed = max(0, (now() - date).total_seconds() / 3600)
    prior_code = civic_memory_reference(incident)
    recalc = apply_memory_bonus(score(incident.description, incident.category_key, len(incident.reports), elapsed), prior_code)
    # Explicitly prefer the higher current risk as time elapses.
    data = {
        "id": incident.id,
        "code": f"CR-{incident.id:04d}",
        "title": incident.title,
        "description": incident.description,
        "ward": incident.ward,
        "location": incident.location,
        "lat": incident.lat,
        "lon": incident.lon,
        "category": incident.category,
        "category_key": incident.category_key,
        "department": incident.department,
        "ai_confidence": incident.confidence,
        "priority": recalc["score"],
        "priority_label": recalc["label"],
        "priority_reasons": recalc["reasons"],
        "status": incident.status,
        "assigned_to": incident.assigned_to,
        "report_count": len(incident.reports),
        "created_at": dt_str(incident.created_at),
        "updated_at": dt_str(incident.updated_at),
        "signal_level": "Amplifying" if len(incident.reports)>=3 else "Emerging" if len(incident.reports)==2 else "Single report",
        "resolution_round": incident.resolution_round,
        "recurrence_of": prior_code,
        "root_cause_review": bool(prior_code),
    }
    if expanded:
        data["reports"] = [{"name":r.reporter_alias,"description":r.description,"date":dt_str(r.created_at)} for r in sorted(incident.reports,key=lambda x:x.created_at)]
        data["timeline"] = [{"kind":e.kind,"actor":e.actor,"note":e.note,"attachment":e.attachment,"date":dt_str(e.created_at)} for e in sorted(incident.events,key=lambda x:x.created_at,reverse=True)]
        data["verifications"] = [{"name":v.reporter_alias,"verdict":v.verdict,"note":v.note,"round":v.round_no,"date":dt_str(v.created_at)} for v in incident.verifications]
    return data


def get_incident(db, id):
    incident = db.scalars(select(Incident).where(Incident.id==id).options(selectinload(Incident.reports), selectinload(Incident.events), selectinload(Incident.verifications))).first()
    if not incident: raise HTTPException(404,"Incident not found")
    return incident


def seed(db):
    if db.scalar(select(func.count(Incident.id))) != 0:
        return
    samples = [
        ("Priya", "The water pipeline has burst beside a school and is flooding the main street. Children cannot cross safely.","Peelamedu","School Road near PSG", "assigned", 5, ["Arjun", "Meera"]),
        ("Karthik", "Streetlights are broken on the busy road near the bus stand and the crossing is unsafe after dark.","Gandhipuram","Cross Cut Road", "in_progress", 12, ["Nila"]),
        ("Anjali", "Garbage has not been collected for days and waste piles are growing beside homes.","RS Puram","DB Road", "reported", 20, []),
        ("Rahul", "A large pothole in the road near the market caused a bike accident and needs urgent attention.","Ukkadam","Market junction", "verification", 26, ["Fathima"]),
        ("Maya", "Playground equipment in the public park was broken and dangerous for children.","Saibaba Colony","Bharathi Park", "resolved", 45, []),
        ("Dev", "Mosquito breeding in stagnant water near the clinic is creating a dengue risk for residents.","Singanallur","Clinic Lane", "reported", 3, ["Sara", "Vijay", "Ishaan"]),
    ]
    base = now()
    for n,(person,description,ward,location,status,hours,additional) in enumerate(samples):
        result=analyze(description, 1 + len(additional), hours)
        incident = Incident(title=description[:95].rstrip(".")+".",description=description,ward=ward,location=location,category_key=result['key'],category=result['category'],department=result['department'],confidence=result['confidence'],priority=result['score'],priority_label=result['label'],reasons_json=json.dumps(result['reasons']),status=status,assigned_to="Civic Works Team" if status in ("assigned","in_progress","verification","resolved") else "", resolution_round=1 if status in ("verification","resolved") else 0,created_at=base-timedelta(hours=hours),updated_at=base-timedelta(hours=max(0,hours-1)))
        db.add(incident)
        db.flush()
        db.add(Report(incident_id=incident.id,reporter_alias=person,description=description,created_at=base-timedelta(hours=hours)))
        for i,alias in enumerate(additional):
            db.add(Report(incident_id=incident.id,reporter_alias=alias,description=f"I also experienced this issue near {location}.",created_at=base-timedelta(hours=hours-i-1)))
        event(db,incident,"reported",person,"Citizen reported the civic problem")
        if additional: event(db,incident,"signal","Civic Signal Fusion",f"{len(additional)} additional resident reports linked to one incident")
        if status in ("assigned","in_progress","verification","resolved"):
            event(db,incident,"assigned","Demo Officer","Department accepted incident for inspection")
        if status in ("in_progress","verification","resolved"):
            event(db,incident,"started","Demo Officer","Team began on-ground repair work")
        if status in ("verification","resolved"):
            event(db,incident,"verification","Demo Officer","Repair completed and evidence recorded. Residents asked to check the actual outcome.")
        if status == "resolved":
            db.add(Verification(incident_id=incident.id,reporter_alias=person,round_no=1,verdict="confirm",note="The playground equipment is now repaired and safely usable."))
            event(db,incident,"confirmed",person,"Citizen confirmed repair quality; outcome verified")
    db.commit()


def create_app(database_url=None, seed_demo=True):
    SessionMaker, engine = make_session(database_url)
    @asynccontextmanager
    async def lifespan(app):
        if seed_demo:
            with SessionMaker() as db: seed(db)
        yield
        engine.dispose()
    app = FastAPI(title="CivicResolve NEXUS",version="1.2.0",description="Impact-led civic incident intelligence with citizen-verified closure",lifespan=lifespan)
    # Sign sessions with a secret that persists between restarts in hosted mode.
    # In production configure SESSION_SECRET and DEMO_MODE=false.
    demo_mode = os.environ.get("DEMO_MODE", "true").lower() == "true"
    secret = os.environ.get("SESSION_SECRET")
    if not secret and not demo_mode:
        raise RuntimeError("SESSION_SECRET must be configured outside demo mode")
    app.add_middleware(SessionMiddleware, secret_key=secret or "LOCAL-DEMO-ONLY-REPLACE-BEFORE-PUBLIC-DEPLOY", same_site="lax", https_only=os.environ.get("COOKIE_SECURE", "false").lower()=="true", max_age=43200)
    attempts = defaultdict(list)

    @app.middleware("http")
    async def security_headers(request:Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; font-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
        return response

    def current_role(request:Request):
        return request.session.get("role", "citizen")

    def require_officer(request:Request):
        if current_role(request) not in ("officer", "admin"):
            raise HTTPException(403, "Officer or administrator sign-in required")
        csrf = request.headers.get("x-csrf-token", "")
        if not csrf or not secrets.compare_digest(csrf, request.session.get("csrf", "")):
            raise HTTPException(403, "Missing or invalid session verification token")
        return request.session.get("name", "Officer")

    @app.get("/api/auth/me")
    def auth_me(request:Request):
        return {"role":current_role(request),"name":request.session.get("name","Citizen"),"csrf":request.session.get("csrf", ""),"demo_mode":demo_mode}

    @app.post("/api/auth/login")
    def auth_login(payload:LoginIn,request:Request):
        client = request.client.host if request.client else "unknown"
        recent = [t for t in attempts[client] if time.monotonic()-t < 600]
        attempts[client] = recent
        if len(recent)>=12: raise HTTPException(429, "Too many sign-in attempts, retry later")
        email=payload.email.strip().lower()
        username = "Administrator" if email=="admin@nexus.demo" else "Civic Officer" if email=="officer@nexus.demo" else ""
        expected_password = os.environ.get("DEMO_PASSWORD", "NexusDemo#2026")
        password_ok = hmac.compare_digest(hashlib.sha256(payload.password.encode()).digest(),hashlib.sha256(expected_password.encode()).digest())
        if not (username and password_ok and demo_mode):
            attempts[client].append(time.monotonic())
            raise HTTPException(401,"Invalid demo credentials or demo accounts are disabled")
        request.session.clear()
        request.session.update({"role":"admin" if username=="Administrator" else "officer", "name":username,"csrf":secrets.token_urlsafe(24)})
        return {"role":request.session["role"],"name":username,"csrf":request.session["csrf"]}

    @app.post("/api/auth/logout")
    def auth_logout(request:Request):
        request.session.clear()
        return {"ok":True}

    app.state.SessionMaker = SessionMaker
    app.mount("/static", StaticFiles(directory=ROOT / "static"),name="static")
    app.mount("/uploads", StaticFiles(directory=MEDIA),name="uploads")

    def db_session():
        with SessionMaker() as db: yield db

    @app.get("/",include_in_schema=False)
    def home(): return FileResponse(ROOT / "static" / "index.html")

    @app.get("/api/health")
    def health(): return {"status":"ok","service":"CivicResolve NEXUS","version":"1.2.0","mode":"demonstration" if demo_mode else "restricted"}

    @app.get("/api/meta")
    def metadata(): return {"wards":WARD_CHOICES,"features":["local_nlp_classification","incident_fusion","explainable_risk","citizen_verification","early_warning"]}

    @app.post("/api/triage")
    def triage(payload:PreviewIn):
        return analyze(payload.description)

    @app.get("/api/incidents")
    def incidents(status:str="all", category:str="all", ward:str="all", q:str="", db:Session=Depends(db_session)):
        items=db.scalars(select(Incident).options(selectinload(Incident.reports), selectinload(Incident.events))).all()
        data=[show(i) for i in items]
        if status!="all": data=[i for i in data if i['status']==status]
        if category!="all": data=[i for i in data if i['category_key']==category]
        if ward!="all": data=[i for i in data if i['ward']==ward]
        if q: data=[i for i in data if q.lower() in (i['description']+' '+i['location']+' '+i['ward']+' '+i['code']).lower()]
        return sorted(data,key=lambda i:(i['status']=="resolved", -i['priority'],i['id']))

    @app.get("/api/incidents/{incident_id}")
    def incident_detail(incident_id:int,db:Session=Depends(db_session)):
        return show(get_incident(db,incident_id),True)

    @app.get("/api/overview")
    def overview(db:Session=Depends(db_session)):
        items=db.scalars(select(Incident).options(selectinload(Incident.reports), selectinload(Incident.events))).all()
        data=[show(i) for i in items]
        active=[i for i in data if i['status']!="resolved"]
        cats={}; wards={}; statuses={}
        for i in data:
            cats[i['category']]=cats.get(i['category'],0)+1
            wards[i['ward']]=wards.get(i['ward'],0)+1
            statuses[i['status']]=statuses.get(i['status'],0)+1
        # Signal radar reports observations, not a predictive forecast.
        alerts=[{"incident":i,"reason":("Multiple independent reports are accumulating" if i['report_count']>=2 else "High-severity safety signal requires inspection")} for i in active if i['report_count']>=2 or i['priority']>=78]
        alerts.sort(key=lambda a:(-a['incident']['report_count'],-a['incident']['priority']))
        memory=[{"incident":i,"prior_code":i["recurrence_of"],"reason":"A new report resembles a previously citizen-verified fix in the same ward and landmark. Root-cause inspection recommended, not assumed."} for i in data if i["recurrence_of"]]
        return {"stats":{"incidents":len(data),"active":len(active),"voices":sum(i['report_count'] for i in data),"awaiting_verification":statuses.get('verification',0),"verified_fixes":statuses.get('resolved',0),"signal_clusters":sum(1 for i in active if i['report_count']>=2),"recurrences_flagged":len(memory)},"categories":cats,"wards":wards,"statuses":statuses,"radar":alerts,"civic_memory":memory,"queue":sorted(active,key=lambda i:-i['priority'])[:6],"methodology":"Transparent rule-based safety score with capped report weighting; local ML suggests category. Recurrence adds at most +10 points for human review; it does not establish a common root cause."}

    @app.post("/api/complaints",status_code=201)
    def submit(payload:ComplaintIn,db:Session=Depends(db_session)):
        a = analyze(payload.description)
        candidate = None; best=0.0
        # Merge only genuinely similar reports in the SAME ward, category and place.
        existing=db.scalars(select(Incident).where(Incident.ward==payload.ward,Incident.category_key==a['key'],Incident.status!='resolved').options(selectinload(Incident.reports))).all()
        for i in existing:
            place_match = not payload.location or not i.location or similarity(payload.location,i.location)>=0.36
            if not place_match: continue
            sim=similarity(payload.description,i.description)
            if sim>best and sim>=0.48:
                best=sim;candidate=i
        if candidate:
            if any(r.reporter_alias.casefold()==payload.name.casefold() for r in candidate.reports):
                raise HTTPException(409,"You already reported this incident. Open its tracking page instead.")
            db.add(Report(incident_id=candidate.id,reporter_alias=payload.name,description=payload.description))
            db.flush()
            event(db,candidate,"signal","Civic Signal Fusion",f"A new resident report was linked (text similarity: {best:.2f}).")
            candidate.updated_at=now()
            id=candidate.id; merged=True
        else:
            prior = recurrence_candidate(db, payload, a['key'])
            prior_code = f"CR-{prior.id:04d}" if prior else None
            reviewed = apply_memory_bonus(score(payload.description, a['key']), prior_code)
            incident=Incident(title=payload.description[:95].rstrip(".")+".",description=payload.description,ward=payload.ward,location=payload.location,lat=payload.lat,lon=payload.lon,category_key=a['key'],category=a['category'],department=a['department'],confidence=a['confidence'],priority=reviewed['score'],priority_label=reviewed['label'],reasons_json=json.dumps(reviewed['reasons']))
            db.add(incident);db.flush()
            db.add(Report(incident_id=incident.id,reporter_alias=payload.name,description=payload.description))
            event(db,incident,"reported",payload.name,"New citizen report received; awaiting officer review")
            if prior_code:
                event(db, incident, "recurrence", "Civic Memory Intelligence", f"Possible recurrence of previously verified {prior_code}; matched category, ward, landmark and description. Check root cause in person.")
            id=incident.id;merged=False
        db.commit()
        return {"incident_id":id,"code":f"CR-{id:04d}","merged":merged,"recurrence_of":prior_code if not merged else None,"triage":a,"message":"Report linked to an existing civic incident" if merged else "New civic incident created"}

    @app.post("/api/incidents/{incident_id}/support")
    def support(incident_id:int,payload:SupportIn,db:Session=Depends(db_session)):
        i=get_incident(db,incident_id)
        if i.status=="resolved":raise HTTPException(409,"Incident already verified as resolved; submit a new complaint if the issue returned")
        if any(r.reporter_alias.casefold()==payload.name.casefold() for r in i.reports):raise HTTPException(409,"This alias has already confirmed the issue")
        db.add(Report(incident_id=i.id,reporter_alias=payload.name.strip(),description=payload.note.strip()))
        event(db,i,"signal",payload.name,"Another citizen corroborated this civic incident")
        db.commit()
        return {"ok":True,"message":"Your observation is now linked to this incident"}

    @app.post("/api/incidents/{incident_id}/action")
    def action(incident_id:int,payload:ActionIn,db:Session=Depends(db_session),officer:str=Depends(require_officer)):
        i=get_incident(db,incident_id)
        allowed={"assign":("reported","reopened"),"start":("assigned",),"request_verification":("in_progress",)}
        if i.status not in allowed[payload.action]:raise HTTPException(409,f"Cannot {payload.action.replace('_',' ')} from '{i.status}' status")
        if payload.action=="assign":
            i.status="assigned"
            i.assigned_to=payload.actor.strip()
            if payload.department: i.department=payload.department.strip()
            kind="assigned"
        elif payload.action=="start":
            i.status="in_progress";kind="started"
        else:
            if len(payload.note.strip())<20:raise HTTPException(422,"Resolution description must be at least 20 characters")
            i.status="verification";i.resolution_round+=1;kind="verification"
        i.updated_at=now();event(db,i,kind,payload.actor.strip(),payload.note.strip());db.commit()
        return {"ok":True,"status":i.status,"message":"Action recorded with an audit event"}

    @app.post("/api/incidents/{incident_id}/verify")
    def verify(incident_id:int,payload:VerifyIn,db:Session=Depends(db_session)):
        i=get_incident(db,incident_id)
        if i.status!="verification":raise HTTPException(409,"This incident is not awaiting citizen verification")
        if not any(r.reporter_alias.casefold()==payload.name.strip().casefold() for r in i.reports):
            raise HTTPException(403,"For this demo, use an alias that submitted or corroborated this incident")
        if any(v.round_no==i.resolution_round and v.reporter_alias.casefold()==payload.name.strip().casefold() for v in i.verifications):
            raise HTTPException(409,"This reporter already verified this resolution round")
        db.add(Verification(incident_id=i.id,reporter_alias=payload.name.strip(),round_no=i.resolution_round,verdict=payload.verdict,note=payload.note.strip()))
        if payload.verdict=="confirm":
            i.status="resolved";kind="confirmed"
        else:
            i.status="reopened";kind="disputed"
        i.updated_at=now();event(db,i,kind,payload.name.strip(),payload.note.strip());db.commit()
        return {"ok":True,"status":i.status,"message":"Outcome verification recorded"}

    @app.post("/api/incidents/{incident_id}/evidence")
    async def upload_evidence(incident_id:int,kind:Literal["before","after"],name:str,file:UploadFile=File(...),db:Session=Depends(db_session),officer:str=Depends(require_officer)):
        i=get_incident(db,incident_id)
        if kind=="after" and i.status not in ("in_progress","verification"):
            raise HTTPException(409,"After images may be attached during or after repair work")
        if file.content_type not in ("image/jpeg","image/png","image/webp"):
            raise HTTPException(415,"Only JPEG, PNG or WebP files are accepted")
        data=await file.read(2_000_001)
        if len(data)>2_000_000:raise HTTPException(413,"Maximum image size is 2 MB")
        if len(data)<16:raise HTTPException(422,"File appears empty")
        signatures={"image/jpeg":data.startswith(b"\xff\xd8\xff"),"image/png":data.startswith(b"\x89PNG\r\n\x1a\n"),"image/webp":data[:4]==b"RIFF" and data[8:12]==b"WEBP"}
        if not signatures[file.content_type]: raise HTTPException(415, "Invalid image file signature")
        ext={"image/jpeg":"jpg","image/png":"png","image/webp":"webp"}[file.content_type]
        path=MEDIA/f"incident-{i.id}-{uuid.uuid4().hex[:12]}.{ext}"
        path.write_bytes(data)
        event(db,i,"evidence",name[:45].strip() or "Contributor",f"{kind.title()}-repair evidence attached",f"/uploads/{path.name}")
        db.commit()
        return {"ok":True,"url":f"/uploads/{path.name}"}

    @app.get("/api/memory")
    def civic_memory(db:Session=Depends(db_session)):
        """Public audit-backed repeat-issue indicators; not a causality predictor."""
        incidents=db.scalars(select(Incident).options(selectinload(Incident.reports), selectinload(Incident.events))).all()
        memory=[{"incident":show(i),"previous_code":civic_memory_reference(i)} for i in incidents if civic_memory_reference(i)]
        return {"count":len(memory),"possible_recurrences":memory,"disclaimer":"A similarity-based alert for human investigation, not proof of a shared root cause."}

    @app.post("/api/assistant")
    def civic_guide(payload:AssistantIn,db:Session=Depends(db_session)):
        """Transparent context-aware service assistant; no external LLM or secret needed."""
        msg = payload.message.strip()
        low = msg.lower()
        role_context = "reporter"
        if payload.incident_id:
            current = get_incident(db,payload.incident_id)
        else:
            current = None
        if current and any(t in low for t in ("repeat", "recurring", "recurrence", "memory", "root cause")):
            code=civic_memory_reference(current)
            return {"intent":"civic_memory","answer":(f"{show(current)['code']} has a possible recurrence link to {code}. The system matched ward, category, landmark and wording after a previously verified fix. A field team should investigate the cause; a text match is not proof." if code else f"No prior verified case is currently linked to {show(current)['code']}. This does not rule out past problems outside the demo data."),"suggestions":["How is priority decided?","How is a fix verified?"]}
        if any(t in low for t in ("repeat", "recurring", "recurrence", "memory", "root cause")):
            rows=db.scalars(select(Incident).options(selectinload(Incident.reports),selectinload(Incident.events))).all()
            found=[show(i) for i in rows if civic_memory_reference(i) and (payload.ward=='all' or i.ward==payload.ward)]
            if not found: return {"intent":"civic_memory","answer":"Civic Memory has not flagged any possible recurring failures in this area yet. To test it, submit a new report resembling a previously citizen-verified incident in the same ward and landmark.","suggestions":["Show urgent cases","How do I report an issue?"]}
            return {"intent":"civic_memory","answer":"Possible repeat issues for human root-cause review: "+"; ".join(f"{i['code']} may follow {i['recurrence_of']} in {i['ward']}" for i in found[:4])+". These are similarity alerts, not diagnoses.","suggestions":["Show urgent cases","How is priority decided?"]}
        if current and any(t in low for t in ("why", "priority", "score", "urgent", "critical")):
            d=show(current)
            return {"intent":"explain_priority", "answer":f"{d['code']} is {d['priority_label'].lower()} priority ({d['priority']}/100). " + "; ".join(d['priority_reasons'][:-1]) + ". The score supports human review, not an emergency determination.","suggestions":["How can I track a complaint?","How is a fix verified?"]}
        if current and any(t in low for t in ("status", "progress", "what happened", "update", "track")):
            d=show(current)
            return {"intent":"track", "answer":f"{d['code']} is currently {d['status'].replace('_',' ')}. Suggested department: {d['department']}. {d['report_count']} citizen report(s) are linked. The incident was last updated {d['updated_at'][:10]}.","suggestions":["Why is it high priority?","How is a fix verified?"]}
        if any(t in low for t in ("verify", "reopen", "fix", "resolved", "dispute", "closed")):
            return {"intent":"verification", "answer":"A repair is not treated as a verified outcome until a reporter confirms it. Officers mark work ready for verification with an evidence note. Reporting citizens can confirm the fix or dispute it to reopen the incident. A dispute returns it to the officer queue.","suggestions":["Show urgent cases","How do I report an issue?"]}
        if any(t in low for t in ("report", "complain", "submit", "new issue", "file")):
            return {"intent":"reporting", "answer":"Use Report an Issue. Describe what happened and where, then choose a ward and optional street/location. NEXUS predicts the service department and explains potential risk. Similar reports in the same area may be combined so the city sees a shared incident. If there is immediate danger, contact local emergency services directly.","suggestions":["Show urgent cases","How is priority decided?"]}
        if any(t in low for t in ("urgent", "high", "critical", "risk", "attention", "radar", "queue", "hotspot", "where")):
            rows=db.scalars(select(Incident).options(selectinload(Incident.reports))).all()
            rows=[show(i) for i in rows if i.status!='resolved' and (payload.ward=='all' or i.ward==payload.ward)]
            rows.sort(key=lambda x:-x['priority'])
            if not rows: return {"intent":"radar", "answer":"No active incidents in that area yet. Report a local issue to begin monitoring.","suggestions":["How do I report an issue?"]}
            top=rows[:3]
            detail="; ".join(f"{i['code']} ({i['ward']}, {i['priority_label']} {i['priority']}/100, {i['report_count']} report(s))" for i in top)
            return {"intent":"radar", "answer":f"Based on currently reported incidents, the top {len(top)} cases to review are: {detail}. These are observation-based alerts, not forecasts. Officers should validate severity on the ground.","suggestions":["How is priority decided?","How can I track a complaint?"]}
        if any(t in low for t in ("score", "priority", "how decide", "fair", "bias", "logic")):
            return {"intent":"methodology", "answer":"NEXUS uses an explainable score: service baseline + potential safety hazards (+23) + sensitive settings (+12) + urgency language (+8) + capped independent reports (up to +12) + waiting-time escalation (up to +20) + possible recurrence review (+10). Report count is capped so quieter neighbourhoods are not automatically deprioritized. Scores are advisory and may be reviewed by humans.","suggestions":["Show urgent cases","How is a fix verified?"]}
        if len(msg)>25 and any(t in low for t in ("water","road","pothole","street","garbage","drain","power","park","mosquito","pipe","leak","குப்பை","தண்ணீர்")):
            a=analyze(msg)
            return {"intent":"triage", "answer":f"Your description suggests {a['category']} → {a['department']}. Preliminary priority: {a['label']} ({a['score']}/100). Why: "+"; ".join(a['reasons'][:-1])+". This is a preliminary suggestion; use Report an Issue to submit it.","triage":a,"suggestions":["How do I report an issue?","Show urgent cases"]}
        return {"intent":"help", "answer":"I'm CivicGuide, a context-aware helper for civic service requests. I can help you report issues, explain priority scores, identify active incidents in a ward, track a selected case or understand citizen-verified closure. I do not make binding municipal decisions.","suggestions":["Show urgent cases","How do I report an issue?","How is priority decided?"]}

    return app

app=create_app()
