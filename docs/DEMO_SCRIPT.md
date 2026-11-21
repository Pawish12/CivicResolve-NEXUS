# Five-minute judge demo

## 0:00–0:40 — Promise and context

Open **Command Center**. "A city should not optimize for closing tickets. It should optimize for verified public outcomes." Briefly identify six fictional sample incidents, community signals, and the queue. All numbers in the demo come from the internal sample database.

## 0:40–1:40 — Live AI and risk explanation

Navigate to **Report an Issue**. Use display name `Demo Reporter`, ward `Town Hall`, landmark `Demo School Road`, and the message:

> A water pipeline burst beside the school on Demo School Road. Flooding is making it unsafe for children to cross.

As you type, the local text model proposes the category and an impact score with explicit reasons. Submit and note the tracking code. Repeat with the same location/description and name `Another Resident` to show **Signal Fusion**. The incident should have two reports but one issue record.

## 1:40–2:35 — Operational action and verification

Click **Citizen view** and sign in as `officer@nexus.demo` / `NexusDemo#2026`. Go to Officer Workspace. Open the newly reported case and **Assign** (record note), **Start work** (record note), **Submit repair for verification** (at least 20 characters describing repairs). Observe a permanent audit trail and the "awaiting verification" status. Photos are optional.

## 2:35–3:25 — The key novelty

Without signing in again, open the incident, enter the reporter alias `Demo Reporter` under **Resident verification**, select **Dispute**, and write "The road is still flooding and the repaired pipe leaks." The case changes to **Reopened**, **not Resolved**. This is the core closed-loop innovation. Repeat the officer flow to create a second repair round; then confirm as `Demo Reporter` to reach **Verified resolved**.

## 3:25–4:15 — Contextual assistant and radar

Open **CivicGuide AI**, ask **Show urgent cases**. Ask **How is priority decided?**. Explain that the answers use current database context and transparent rules, not an external paid LLM. Then show Signal Radar to illustrate how repeated reports become a warning signal.

## 4:15–5:00 — Impact, evaluation and limitations

Open **City Intelligence** and explain what incident fusion, dispute counts and verified fixes measure. Summarize: citizen intake → explainable AI → signal fusion → officer repair → citizen feedback → verified completion or reopening. Mention the sample data, heuristic scoring, limited identity assurance, and real-world next steps. End with the **live deployment** URL and public `.git` repository link.

## Backup for unstable event Wi-Fi

Run the local demo via `python -m uvicorn app.main:app --port 8000` before presentation. No paid model or internet service is needed once Python dependencies are installed. The official submission, however, still **requires a working publicly accessible deployment**.
