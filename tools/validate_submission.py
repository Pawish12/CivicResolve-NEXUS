"""Offline checks before publishing the hackathon repository.

Usage: python tools/validate_submission.py
This cannot confirm public GitHub visibility, working hosting, or LinkedIn status.
"""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
EXCLUDES = {'.git', '.venv', 'venv', '__pycache__', '.pytest_cache', 'data', '.idea', '.vscode', 'coverage', 'node_modules'}
REQUIRED = ['README.md', '.gitignore', 'requirements.txt', 'app/main.py', 'app/triage.py', 'app/database.py', 'app/static/index.html', 'app/static/app.js', 'app/static/style.css', 'tests/test_workflows.py', 'docs/LINKEDIN_POST.md', 'docs/SUBMISSION_CHECKLIST.md']
MAX = 10_000_000
files = [p for p in ROOT.rglob('*') if p.is_file() and not any(component in EXCLUDES for component in p.relative_to(ROOT).parts) and p.name != 'civicresolve.db' and p.suffix not in ('.pyc', '.db', '.sqlite3', '.log')]
size = sum(p.stat().st_size for p in files)
issues=[]
for name in REQUIRED:
    if not (ROOT/name).is_file(): issues.append(f'Missing file: {name}')
if size>=MAX: issues.append(f'Repository source files total {size:,} bytes, over the 10MB limit')
for p in files:
    if p.name == '.env': issues.append('Actual .env included; must be removed')
print('CIVICRESOLVE NEXUS — SUBMISSION PRE-CHECK')
print('-'*49)
print(f'Files (excluding generated folders): {len(files)}')
print(f'Source size: {size:,} bytes ({size/1_000_000:.3f} MB) / 10 MB max')
print(f'Source-size check: {"PASS" if size<MAX else "FAIL"}')
try:
    branches = subprocess.check_output(['git','branch','--format=%(refname:short)'],cwd=ROOT,stderr=subprocess.DEVNULL,text=True).splitlines()
    if not branches: print('Branches: no local commit yet; initialize main then commit')
    else:
        print(f'Local branches: {branches}')
        if branches!=['main']:issues.append('Exactly one branch called main is required')
except (OSError, subprocess.CalledProcessError):
    print('Branches: Git not initialized (normal for ZIP before publishing)')
print('Public GitHub .git URL: NOT VERIFIED — check on GitHub')
print('Live deployed URL: NOT VERIFIED — check in a browser')
print('LinkedIn post URL: NOT VERIFIED — publish and copy the post link')
print('Required files:', 'PASS' if not [x for x in issues if x.startswith('Missing')] else 'FAIL')
if issues:
    print('ISSUES:')
    for issue in issues:print(' -',issue)
    sys.exit(1)
print('Local source checks: PASS')
