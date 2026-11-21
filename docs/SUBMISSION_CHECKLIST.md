# Hackathon submission checklist — CivicResolve NEXUS

**Official challenge vertical:** CivicResolve: AI-Powered Citizen Grievance Management and Resolution.

> Status: **code and test package prepared locally.** It is **not yet published** to GitHub, deployed, or posted to LinkedIn. These require the participant's authenticated accounts and action.

## Required fields on the competition form

| Submission field | Required content | Current state |
|---|---|---|
| Challenges | Select **CivicResolve: AI-Powered Citizen Grievance Management and Resolution** | Challenge identified |
| Public GitHub Repository Link | `https://github.com/YOUR-USERNAME/CivicResolve-NEXUS.git` | **Not yet created; URL is only an example** |
| Deployed Link / Cloud Run URL | `https://YOUR-LIVE-APP.example` | **Not yet deployed; URL is only an example** |
| LinkedIn Post | Full public URL of a post about this particular challenge solution | **Not yet published** |

**Do not paste the placeholder URLs above into the real form.**

## Rule-by-rule actions

- [x] Project architecture and code completed in the ZIP.
- [x] `README.md` describes the chosen vertical, approach/logic, workflow and assumptions.
- [x] Tests included and run.
- [x] `.gitignore` excludes `data`, `civicresolve.db`, `.venv`, test caches and `.env`.
- [ ] Extract the ZIP and inspect source code before publishing.
- [ ] Confirm that Git is installed: `git --version`.
- [ ] Confirm GitHub account can create/manage public repositories.
- [ ] Create a **new, empty PUBLIC** GitHub repository named `CivicResolve-NEXUS` (do not initialize a README or license there, since local files already exist).
- [ ] Commit and push exactly one local branch called `main`.
- [ ] Verify branch count on GitHub = **1**, including no auto-created remote alternate branch.
- [ ] Confirm the repository's tracked source is **strictly under 10 MB**; it should be < 1 MB as provided.
- [ ] Confirm the cloned URL **explicitly ends with `.git`**.
- [ ] Deploy via your preferred host and verify its public URL in a private/incognito browser.
- [ ] Test a citizen submission, officer workflow, and CivicGuide on the public URL.
- [ ] Capture screenshots from the running application, add them to README if desired (ensure total repo stays <10 MB).
- [ ] Publish the project-specific LinkedIn post from `docs/LINKEDIN_POST.md`, and copy the post URL.
- [ ] Enter the real GitHub `.git`, live app, and LinkedIn links into the portal.
- [ ] Submit before the event deadline; maximum **2 scored attempts** and **only the latest attempt counts**.

### One-branch GitHub push commands

Run in an extracted project folder from PowerShell, Git Bash, WSL or Linux:

```bash
git init -b main
git add .
git commit -m "Build CivicResolve NEXUS hackathon MVP"
git remote add origin https://github.com/YOUR-USERNAME/CivicResolve-NEXUS.git
git push -u origin main
```

Replace `YOUR-USERNAME` with **your actual GitHub user name**. GitHub must already have an empty public repo with that exact name. If `git init` reports the repo is already initialized, do not create or push extra branches. `git push` uses authenticated Git credentials; a password entered at a command prompt may require a Personal Access Token or GitHub's credential helper.

### Inspect branch/size before submission

```bash
git branch --list
git ls-files | wc -l
# Windows PowerShell: (git ls-files | Measure-Object).Count
```

Repository size can be checked on GitHub after push. If an image or dependency accidentally makes it exceed 10 MB, remove it **from Git history** before submitting; simply deleting a tracked file after committing might not reduce repository storage sufficiently. Avoid new branches when fixing it.

## Organizer timing from screenshots

- Build phase: Saturday, November 21, 2026, 8:00–8:30 AM IST.
- Submission: Saturday, November 21, 2026, 8:30 AM–5:00 PM IST.
- Evaluation: Saturday 5:00 PM through Sunday 5:00 PM IST.
- Winners announcement: Sunday, November 22, 2026, 5:00–5:30 PM IST.

## Pre-deployment audit

```bash
python -m pytest -q
python -m uvicorn app.main:app --port 8000
```

Check `http://localhost:8000/api/health`, then interact with `http://localhost:8000/`.

## Requirements-to-evidence map

| High-value evaluation focus | Demonstrable evidence |
|---|---|
| Smart dynamic assistant | `/api/assistant` uses live incident/ward data and explains why/what to do |
| Contextual logic | ML classification + explicit scoring + risk/age/crowd data + incident-based guidance |
| Practical usability | Full citizen reporting → staff action → resident resolution feedback |
| Clean code | Separate API, data and triage modules; tests and docs |
| Security | Session-protected officer actions, CSRF, validation, file signature checks, CSP; **demo-only credentials and aliases are disclosed limitations** |
| Efficiency | No frontend toolchain, in-process text classification, no paid inference, tiny repo |
| Testing | Repeatable `pytest` suite and `docs/DEMO_SCRIPT.md` |
| Accessibility | Keyboardable incident cards, form labels, focus and reduced-motion styles |
| Alignment | All workflows support CivicResolve grievance-management challenge |

## Common mistakes

- Submitting a **non-working deployment** (may be disqualified).
- Using the **GitHub browser URL without `.git`** (specifically forbidden in the organizer instructions).
- Creating a second Git branch by accident; all work must stay on `main`.
- Committing `.venv/`, a model cache, screenshots totaling >10MB or a real database.
- Copying a LinkedIn **profile** URL rather than the link to the specific post.
- Claiming that synthetic pilot data represents real municipal reports.
