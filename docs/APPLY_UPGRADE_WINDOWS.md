# Apply the CivicResolve NEXUS upgrade on Windows

**Important:** Keep your successful 95.17 first hackathon attempt. A second scored attempt replaces it under the event rules, so only submit again after verification. There is no guaranteed score improvement.

## Step 1 — Open the existing local project

In VS Code, open the folder ending in:

`C:\Users\pawis\Downloads\CivicResolve-NEXUS-Hackathon-Submission\CivicResolve-NEXUS`

Open **Terminal → New Terminal** (PowerShell). The terminal prompt should end in `\CivicResolve-NEXUS>`.

## Step 2 — Check that your current code is saved

Run `git status --short`. No output is ideal. If there are uncommitted changes, save or review them before applying the update.

## Step 3 — Extract the patch over that project

Download `CivicResolve-NEXUS-Upgrade-Patch.zip` to your Downloads folder, then run this PowerShell command **from within the existing CivicResolve-NEXUS project directory**:

```powershell
Expand-Archive -LiteralPath "$env:USERPROFILE\Downloads\CivicResolve-NEXUS-Upgrade-Patch.zip" -DestinationPath . -Force
```

The patch replaces only specific source files, tests and docs. It does not contain a `.git` directory, credentials, or a local SQLite database.

## Step 4 — Run quality gates (before pushing)

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
python tools/validate_submission.py
```

You should see **17 passed** and a successful source check. If tests fail, do not push.

Start the app (`python -m uvicorn app.main:app --reload --port 8000`) and open `http://localhost:8000`.

For the newly introduced Civic Memory demonstration:

1. Open **Report an Issue**.
2. Name: `Novelty Demo`; Ward: `Saibaba Colony`; Landmark: `Bharathi Park`.
3. Description: `Playground equipment in the public park was broken and dangerous for children.`
4. Submit. Open **Signal Radar**. The new incident should indicate a possible recurrence of previous demo case `CR-0005`.
5. Ask **CivicGuide AI**: `Show recurring issues`.

This uses synthetic demo data and a similarity heuristic, **not** verified proof of an underlying root cause.

## Step 5 — Update the existing GitHub repo and Render deployment

Once the application is working locally:

```powershell
git status --short
git add app/main.py app/static/app.js app/static/index.html app/static/style.css requirements.txt tests/test_workflows.py README.md docs/UPGRADE_NOTES.md docs/APPLY_UPGRADE_WINDOWS.md .github/workflows/ci.yml
git commit -m "Add Civic Memory Intelligence and expanded quality gates"
git push origin main
```

Render should redeploy when `main` is updated (if Auto-Deploy is enabled). Verify the deployed site still loads, that the `Civic Memory` section is visible in **Signal Radar**, and that GitHub Actions tests pass. **Updating GitHub does not itself use the second Hack2Skill scored submission**; only pressing Submit on the portal does.

## Step 6 — Decide whether to use the last scored attempt

Your current attempt scored **95.17**. The portal stated that **only your latest attempt counts**. A new assessment can be lower. Review live features, tests, the evaluation criteria, and whether the change justifies taking the risk. If you opt for attempt 2, submit the unchanged GitHub `.git`, Render public URL and LinkedIn post URL after the new deployment is verified.
