import asyncio
import os
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from backend.main import app
from backend.database import Base, get_db, User, Message, Feedback
from backend.ai import answer

HEADERS = {'X-MedAI-Request':'1'}
PASSWORD = 'test-password-123'

@pytest.fixture
def clients(tmp_path):
    engine = create_engine('sqlite:///' + str(tmp_path / 'test.db'), connect_args={'check_same_thread':False})
    Base.metadata.create_all(engine)
    session = sessionmaker(engine, expire_on_commit=False)
    def db_override():
        with session() as db:
            yield db
    app.dependency_overrides[get_db] = db_override
    # No app lifespan here: test database is explicitly initialized above.
    patient = TestClient(app, headers=HEADERS)
    admin = TestClient(app, headers=HEADERS)
    yield patient, admin, session
    patient.close(); admin.close()
    app.dependency_overrides.clear()
    engine.dispose()

def register(client, email='patient@example.com'):
    response = client.post('/api/auth/register', json={'email':email,'full_name':'Test Person','password':PASSWORD,'consent':True})
    assert response.status_code == 201, response.text
    return response.json()

def make_admin(client, session):
    user = register(client, 'admin@example.com')
    with session() as db:
        db.get(User,user['id']).role='admin';db.commit()
    return user

def document(client, approved=False):
    return client.post('/api/admin/documents',json={'title':'Malaria education','category':'Primary care','source':'https://www.who.int/news-room/fact-sheets/detail/malaria','content':'Malaria symptoms can include fever and headache. A healthcare professional can arrange appropriate testing.','approved':approved})

def test_authentication_and_csrf(clients):
    patient, admin, session = clients
    assert patient.get('/api/conversations').status_code == 401
    response=patient.post('/api/auth/register',headers={'X-MedAI-Request':''},json={})
    assert response.status_code==403
    register(patient)
    assert patient.get('/api/auth/me').status_code==200
    assert patient.get('/api/admin/users').status_code==403
    patient.post('/api/auth/logout')
    assert patient.get('/api/auth/me').status_code==401
    assert patient.post('/api/auth/login',json={'email':'patient@example.com','password':'wrong-password'}).status_code==401
    response=patient.post('/api/auth/login',json={'email':'patient@example.com','password':PASSWORD})
    assert response.status_code==200
    assert 'HttpOnly' in response.headers['set-cookie']
    assert 'SameSite=strict' in response.headers['set-cookie']

def test_conversation_ownership_and_feedback(clients):
    patient, other, session=clients
    register(patient);register(other,'other@example.com')
    cid=patient.post('/api/conversations').json()['id']
    result=patient.post(f'/api/conversations/{cid}/messages',json={'message':'Tell me about malaria'}).json()
    assert result['reply']['mode']=='no_evidence'
    assert other.get(f'/api/conversations/{cid}/messages').status_code==404
    assert other.post(f'/api/conversations/{cid}/messages',json={'message':'Hi'}).status_code==404
    assert other.delete(f'/api/conversations/{cid}').status_code==404
    payload={'message_id':result['reply']['id'],'rating':5}
    assert other.post('/api/feedback',json=payload).status_code==404
    assert patient.post('/api/feedback',json=payload).status_code==201
    assert patient.post('/api/feedback',json=payload|{'rating':1}).status_code==201
    with session() as db:
        assert len(list(db.scalars(select(Feedback))))==1
    assert patient.delete(f'/api/conversations/{cid}').status_code==200
    with session() as db:
        assert not list(db.scalars(select(Message)))
        assert not list(db.scalars(select(Feedback)))

def test_document_review_publication_and_deletion(clients):
    patient,admin,session=clients
    register(patient);make_admin(admin,session)
    assert document(patient).status_code==403
    draft=document(admin).json()
    assert patient.get('/api/library').json()==[]
    cid=patient.post('/api/conversations').json()['id']
    def chat(text):return patient.post(f'/api/conversations/{cid}/messages',json={'message':text}).json()['reply']
    assert chat('malaria')['mode']=='no_evidence'
    data={k:draft[k] for k in ['title','category','source','content','approved']};data['approved']=True
    assert admin.put('/api/admin/documents/'+str(draft['id']),json=data).status_code==200
    assert len(patient.get('/api/library').json())==1
    reply=chat('malaria symptoms')
    assert reply['mode']=='evidence' and reply['sources'][0]['id']==draft['id']
    assert chat('It started yesterday')['sources']
    assert admin.delete('/api/admin/documents/'+str(draft['id'])).status_code==200
    assert chat('malaria')['mode']=='no_evidence'

@pytest.mark.parametrize('question',["I can't breathe",'severe chest pain','unconscious','I want to kill myself','severe bleeding'])
def test_emergency_bypasses_inference(question,monkeypatch):
    monkeypatch.setenv('INFERENCE_URL','https://should-not-be-called.invalid')
    result=asyncio.run(answer(question,[],[]))
    assert result['mode']=='emergency' and result['sources']==[]

def test_inference_failure_falls_back_and_unsafe_output_rejected(monkeypatch):
    import httpx
    monkeypatch.setenv('INFERENCE_URL','https://inference.invalid')
    monkeypatch.setenv('INFERENCE_API_KEY','x'*40)
    source=SimpleNamespace(id=1,title='Malaria',category='Health',source='https://example.com',content='Malaria can cause fever. Speak with a clinician about testing.')
    class FakeClient:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,*args,**kwargs):
            return httpx.Response(200,json={'content':'You definitely have malaria. Take 500 mg.', 'sources':[{'id':1}]},request=httpx.Request('POST','https://inference.invalid'))
    monkeypatch.setattr(httpx,'AsyncClient',FakeClient)
    assert asyncio.run(answer('malaria',[],[source]))['mode']=='evidence'
    async def failure(*args,**kwargs):raise httpx.ConnectError('offline')
    monkeypatch.setattr(FakeClient,'post',failure)
    assert asyncio.run(answer('malaria',[],[source]))['mode']=='evidence'

def test_admin_reports_disable_and_validation(clients):
    patient,admin,session=clients
    user=register(patient);admin_user=make_admin(admin,session)
    report=admin.get('/api/admin/reports')
    assert report.status_code==200 and report.json()['users']==2
    assert admin.get('/api/admin/audit').json()
    assert admin.patch('/api/admin/users/'+str(admin_user['id']),json={'active':False}).status_code==400
    assert admin.patch('/api/admin/users/'+str(user['id']),json={'active':False}).status_code==200
    assert patient.get('/api/auth/me').status_code==401
    invalid={'title':'Valid title','category':'Health','source':'javascript:alert(1)','content':'A'*40,'approved':True}
    assert admin.post('/api/admin/documents',json=invalid).status_code==422

def test_rate_limit_and_empty_messages(clients):
    patient,_,_=clients
    register(patient)
    cid=patient.post('/api/conversations').json()['id']
    assert patient.post(f'/api/conversations/{cid}/messages',json={'message':'  '}).status_code==422
    for _ in range(12):
        assert patient.post(f'/api/conversations/{cid}/messages',json={'message':'hello'}).status_code==200
    assert patient.post(f'/api/conversations/{cid}/messages',json={'message':'hello'}).status_code==429

def test_frontend_and_headers(clients):
    patient,_,_=clients
    response=patient.get('/')
    assert response.status_code==200 and 'Your health,' in response.text
    assert response.headers['x-frame-options']=='DENY'
    assert patient.get('/static/app.js').status_code==200
    assert patient.get('/api/health').json()['status']=='ok'

def test_medication_requests_refer_without_inference():
    assert asyncio.run(answer('What dose should I take?',[],[]))['mode']=='referral'
    assert asyncio.run(answer('What dose should I take for severe chest pain?',[],[]))['mode']=='emergency'
