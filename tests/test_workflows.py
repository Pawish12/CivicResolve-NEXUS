"""End-to-end API workflows and responsible-use guardrail checks."""
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.triage import analyze, similarity, score

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('DEMO_MODE','true')
    monkeypatch.setenv('SESSION_SECRET','unit-test-only-secret')
    app=create_app(database_url=f'sqlite:///{tmp_path / "test.db"}',seed_demo=True)
    with TestClient(app) as c:
        yield c


def submit(c,name='Demo Resident',description='A broken water pipeline is flooding the school street and children cannot cross the road safely.',ward='Town Hall',location='Sample Lane'):
    return c.post('/api/complaints',json={'name':name,'description':description,'ward':ward,'location':location})

def auth(c):
    res=c.post('/api/auth/login',json={'email':'officer@nexus.demo','password':'NexusDemo#2026'})
    assert res.status_code==200,res.text
    return res.json()['csrf']

def officer_action(c,id,action,note,csrf):
    return c.post(f'/api/incidents/{id}/action',headers={'X-CSRF-Token':csrf},json={'actor':'Civic Officer','action':action,'note':note})

def test_metadata_health_and_seed_data(client):
    assert client.get('/api/health').json()['status']=='ok'
    overview=client.get('/api/overview').json()
    assert overview['stats']['incidents']==6
    assert overview['stats']['voices']>6
    assert overview['stats']['verified_fixes']==1
    assert len(overview['radar'])>=2
    assert len(client.get('/api/incidents').json())==6


def test_classifier_and_safety_score():
    x=analyze('The road has a major pothole and a child fell off a bike near the school.')
    assert x['key']=='roads'
    assert 0<=x['score']<=100
    y=score('An exposed live wire near the school is unsafe and urgent','lights',1,0)
    assert y['score']>=78
    assert any('safety' in r.lower() for r in y['reasons'])
    assert score('Garbage has not been picked up','waste',100,0)['score']<=40
    assert similarity('Burst water pipe next to school', 'Burst water pipe next to school')==1


def test_report_creation_read_and_fusion(client):
    first=submit(client)
    assert first.status_code==201,first.text
    inc=first.json()['incident_id']
    assert first.json()['merged'] is False
    assert client.get(f'/api/incidents/{inc}').json()['report_count']==1
    second=submit(client,'Another Resident')
    assert second.status_code==201
    assert second.json()['merged'] is True
    assert second.json()['incident_id']==inc
    assert client.get(f'/api/incidents/{inc}').json()['report_count']==2
    third=submit(client,'Another Resident')
    assert third.status_code==409
    assert client.get(f'/api/incidents/{inc}').json()['priority']>=first.json()['triage']['score']


def test_citizens_cannot_change_officer_status(client):
    inc=submit(client).json()['incident_id']
    payload={'actor':'Intruder','note':'Fake repairs have been made','action':'assign'}
    response=client.post(f'/api/incidents/{inc}/action',json=payload)
    assert response.status_code==403
    assert client.get(f'/api/incidents/{inc}').json()['status']=='reported'


def test_officer_login_csrf_and_full_resolution_cycle(client):
    inc=submit(client).json()['incident_id']
    assert client.post('/api/auth/login',json={'email':'officer@nexus.demo','password':'not-the-password'}).status_code==401
    csrf=auth(client)
    assert officer_action(client,inc,'assign','Officer accepted responsibility','incorrect-csrf').status_code==403
    assert officer_action(client,inc,'start','Skipping assignment is blocked',csrf).status_code==409
    assert officer_action(client,inc,'assign','Officer accepted responsibility',csrf).status_code==200
    assert officer_action(client,inc,'start','Field team started inspection',csrf).status_code==200
    assert officer_action(client,inc,'request_verification','Repaired the pipeline, restored water supply and photographed the site.',csrf).status_code==200
    assert client.get(f'/api/incidents/{inc}').json()['status']=='verification'
    # Unrelated aliases cannot approve resolutions.
    assert client.post(f'/api/incidents/{inc}/verify',json={'name':'Stranger','verdict':'confirm','note':'Looks all fixed to me'}).status_code==403
    dispute=client.post(f'/api/incidents/{inc}/verify',json={'name':'Demo Resident','verdict':'dispute','note':'The damaged pipe is still leaking.'})
    assert dispute.status_code==200
    assert dispute.json()['status']=='reopened'
    assert officer_action(client,inc,'assign','Further field repair assigned',csrf).status_code==200
    assert officer_action(client,inc,'start','Repair resumed',csrf).status_code==200
    assert officer_action(client,inc,'request_verification','Second repair completed, seal tested, water leak removed.',csrf).status_code==200
    verify=client.post(f'/api/incidents/{inc}/verify',json={'name':'Demo Resident','verdict':'confirm','note':'The water is no longer leaking.'})
    assert verify.status_code==200
    detail=client.get(f'/api/incidents/{inc}').json()
    assert detail['status']=='resolved'
    assert detail['resolution_round']==2
    assert len(detail['verifications'])==2
    assert client.post(f'/api/incidents/{inc}/support',json={'name':'Late Resident','note':'I also saw this issue'}).status_code==409
    assert client.post('/api/auth/logout').status_code==200
    assert officer_action(client,inc,'assign','Illicit status mutation',csrf).status_code==403


def test_contextual_assistant(client):
    general=client.post('/api/assistant',json={'message':'How do I report an issue?'}).json()
    assert general['intent']=='reporting'
    urgent=client.post('/api/assistant',json={'message':'Show urgent cases'}).json()
    assert urgent['intent']=='radar'
    assert 'CR-' in urgent['answer']
    why=client.post('/api/assistant',json={'message':'Why is this incident high priority?','incident_id':1}).json()
    assert why['intent']=='explain_priority'
    assert 'CR-0001' in why['answer']
    assert client.post('/api/assistant',json={'message':'hi'}).status_code==422


def test_upload_restrictions(client):
    inc=submit(client).json()['incident_id']
    csrf=auth(client)
    # Unauthenticated or wrongly signed uploads are rejected.
    response=client.post(f'/api/incidents/{inc}/evidence?kind=before&name=Somebody',files={'file':('attempt.html',b'<html>fake</html>','image/png')})
    assert response.status_code==403
    # Even an authorized officer cannot upload disguised HTML as a PNG.
    response=client.post(f'/api/incidents/{inc}/evidence?kind=before&name=Officer',headers={'X-CSRF-Token':csrf},files={'file':('bad.png',b'<html>unsafe payload</html>','image/png')})
    assert response.status_code==415


def test_input_validation(client):
    assert submit(client,description='too short').status_code==422
    assert submit(client,description='<script>alert(1)</script>',ward='').status_code==422
    assert client.get('/api/incidents/999999').status_code==404

# --- Upgrade regression tests: recurrent failures, security and inclusion ---

def test_civic_memory_flags_repeat_after_verified_fix(client):
    """A formerly fixed problem must become a *new*, auditable incident."""
    report = client.post('/api/complaints', json={
        'name':'New Demo Resident',
        'description':'Playground equipment in the public park was broken and dangerous for children.',
        'ward':'Saibaba Colony', 'location':'Bharathi Park',
    })
    assert report.status_code == 201
    payload = report.json()
    assert payload['merged'] is False
    assert payload['recurrence_of'] == 'CR-0005'
    issue = client.get(f"/api/incidents/{payload['incident_id']}").json()
    assert issue['status']=='reported'
    assert issue['root_cause_review'] is True
    assert issue['recurrence_of']=='CR-0005'
    assert any('may have recurred' in r for r in issue['priority_reasons'])
    assert any(e['kind']=='recurrence' for e in issue['timeline'])
    memory = client.get('/api/memory')
    assert memory.status_code==200
    assert memory.json()['count']==1
    assert memory.json()['possible_recurrences'][0]['previous_code']=='CR-0005'
    assert client.get('/api/overview').json()['stats']['recurrences_flagged']==1
    guide=client.post('/api/assistant',json={'message':'Show recurring issues'})
    assert guide.json()['intent']=='civic_memory'
    assert 'CR-0005' in guide.json()['answer']


def test_civic_memory_is_conservative_about_locations(client):
    description='Playground equipment in the public park was broken and dangerous for children.'
    wrong_ward = client.post('/api/complaints',json={'name':'New Resident', 'description':description,
                                                    'ward':'Town Hall','location':'Bharathi Park'})
    assert wrong_ward.status_code==201
    assert wrong_ward.json()['recurrence_of'] is None
    wrong_landmark = client.post('/api/complaints',json={'name':'Other Resident','description':description,
                                                        'ward':'Saibaba Colony','location':'Bus stand near Town Hall'})
    assert wrong_landmark.status_code==201
    assert wrong_landmark.json()['recurrence_of'] is None
    assert client.get('/api/memory').json()['count']==0


def test_incident_priority_repeat_bonus_is_bounded(client):
    def recheck(d): return client.post('/api/triage',json={'description':d}).json()
    initial = recheck('Playground equipment in the public park was broken and dangerous for children.')
    report = client.post('/api/complaints',json={'name':'Resident Two',
        'description':'Playground equipment in the public park was broken and dangerous for children.',
        'ward':'Saibaba Colony','location':'Bharathi Park'}).json()
    score = client.get(f"/api/incidents/{report['incident_id']}").json()['priority']
    assert score == min(100,initial['score']+10)
    assert score <= 100


def test_repeat_issue_is_not_merged_into_closed_incident(client):
    res=client.post('/api/complaints',json={'name':'Another Citizen',
        'description':'Playground equipment in the public park was broken and dangerous for children.',
        'ward':'Saibaba Colony','location':'Bharathi Park'})
    assert res.json()['incident_id'] != 5
    assert client.get('/api/incidents/5').json()['status'] == 'resolved'


def test_security_headers_and_main_accessibility_hooks(client):
    home=client.get('/')
    assert home.status_code==200
    assert home.headers['X-Content-Type-Options']=='nosniff'
    assert home.headers['X-Frame-Options']=='DENY'
    assert "frame-ancestors 'none'" in home.headers['Content-Security-Policy']
    assert b'Skip to main content' in home.content
    assert b'aria-modal="true"' in home.content
    js=client.get('/static/app.js').text
    assert 'trapDialogKeys' in js
    assert 'function closeDrawer' in js


def test_login_bruteforce_guard_and_recovery_boundary(client):
    for _ in range(12):
        assert client.post('/api/auth/login',json={'email':'officer@nexus.demo','password':'incorrect-password'}).status_code==401
    limited=client.post('/api/auth/login',json={'email':'officer@nexus.demo','password':'NexusDemo#2026'})
    assert limited.status_code==429


def test_invalid_ward_category_filters_do_not_break_api(client):
    assert client.get('/api/incidents',params={'status':'not-a-real-status'}).json()==[]
    assert client.get('/api/incidents',params={'ward':'not-a-real-ward'}).json()==[]
    assert client.get('/api/incidents',params={'category':'not-a-real-category'}).json()==[]


def test_large_evidence_upload_rejected(client):
    incident=submit(client).json()['incident_id'];token=auth(client)
    image=b'\x89PNG\r\n\x1a\n'+b'0'*2_000_001
    response=client.post(f'/api/incidents/{incident}/evidence?kind=before&name=DemoOfficer',
      headers={'X-CSRF-Token':token},files={'file':('huge.png',image,'image/png')})
    assert response.status_code==413


def test_no_memory_reference_for_nonrepeated_seed_case(client):
    assert client.get('/api/memory').json()['count']==0
    assert client.get('/api/incidents/1').json()['recurrence_of'] is None
    answer=client.post('/api/assistant',json={'message':'Any recurring issues in our city?'}).json()
    assert answer['intent']=='civic_memory'
    assert 'has not flagged' in answer['answer']
