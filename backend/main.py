import json
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, func, delete
from sqlalchemy.exc import IntegrityError
from backend.database import Base, engine, get_db, User, Conversation, Message, Document, Feedback, Audit, PRODUCTION, now
from backend.security import current_user, admin_user, hash_password, verify_password, token_for, DUMMY_HASH, limit
from backend.ai import answer

@asynccontextmanager
async def lifespan(app):
    if not PRODUCTION:
        Base.metadata.create_all(engine)
    yield

app = FastAPI(title='MedAI', version='0.1.0', lifespan=lifespan, docs_url=None if PRODUCTION else '/api/docs', redoc_url=None)

@app.middleware('http')
async def security_headers(request: Request, call_next):
    if request.method in ('POST', 'PUT', 'PATCH', 'DELETE') and request.headers.get('x-medai-request') != '1':
        return Response('Missing request verification header', status_code=403)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    if request.url.path.startswith('/api'):
        response.headers['Cache-Control'] = 'no-store'
    return response

class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=10, max_length=72)

    @field_validator('email')
    @classmethod
    def valid_email(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
            raise ValueError('Enter a valid email address.')
        return value

    @field_validator('password')
    @classmethod
    def valid_password(cls, value):
        if len(value.encode()) > 72:
            raise ValueError('Password must be no more than 72 bytes.')
        return value

class Registration(Credentials):
    full_name: str = Field(min_length=2, max_length=100)
    consent: bool

class ChatInput(BaseModel):
    message: str = Field(min_length=1, max_length=2000)

    @field_validator('message')
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError('Please enter a question.')
        return value.strip()

class DocumentInput(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    category: str = Field(min_length=2, max_length=80)
    source: str = Field(max_length=1000)
    content: str = Field(min_length=30, max_length=30000)
    approved: bool = False

    @field_validator('source')
    @classmethod
    def valid_source(cls, value):
        parsed = urlparse(value)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('Provide an HTTPS source URL without credentials.')
        return value

class FeedbackInput(BaseModel):
    message_id: int
    rating: int = Field(ge=1, le=5)
    comments: str = Field(default='', max_length=1000)

class UserUpdate(BaseModel):
    active: bool

def user_json(user):
    return {'id': user.id, 'full_name': user.full_name, 'email': user.email, 'role': user.role, 'active': user.active}

def message_json(message):
    return {'id': message.id, 'sender': message.sender, 'content': message.content, 'sources': json.loads(message.sources_json), 'mode': message.mode, 'created_at': message.created_at.isoformat()}

def doc_json(doc):
    return {'id': doc.id, 'title': doc.title, 'category': doc.category, 'source': doc.source, 'content': doc.content, 'approved': doc.approved, 'reviewed_at': doc.reviewed_at.isoformat() if doc.reviewed_at else None}

def own_conversation(db, cid, uid):
    conversation = db.get(Conversation, cid)
    if not conversation or conversation.user_id != uid:
        raise HTTPException(404, 'Conversation not found.')
    return conversation

def set_session(response, user):
    response.set_cookie('medai_session', token_for(user), httponly=True, secure=PRODUCTION, samesite='strict', max_age=28800, path='/')

@app.get('/api/health')
def health(db=Depends(get_db)):
    db.execute(select(func.count(User.id)))
    return {'status': 'ok', 'inference_configured': bool(os.getenv('GROQ_API_KEY') or (os.getenv('INFERENCE_URL') and os.getenv('INFERENCE_API_KEY'))), 'version': '0.1.0'}

@app.post('/api/auth/register', status_code=201)
def register(data: Registration, request: Request, response: Response, db=Depends(get_db)):
    limit(db, 'register:' + (request.client.host if request.client else 'unknown'), 10)
    if not data.consent:
        raise HTTPException(400, 'Please acknowledge how your conversation data is used.')
    user = User(full_name=data.full_name.strip(), email=data.email, password_hash=hash_password(data.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'An account already exists for this email.')
    set_session(response, user)
    return user_json(user)

@app.post('/api/auth/login')
def login(data: Credentials, request: Request, response: Response, db=Depends(get_db)):
    limit(db, 'login:' + data.email, 10)
    limit(db, 'login-ip:' + (request.client.host if request.client else 'unknown'), 30)
    user = db.scalar(select(User).where(User.email == data.email))
    valid = verify_password(data.password, user.password_hash if user else DUMMY_HASH)
    if not user or not valid or not user.active:
        raise HTTPException(401, 'Email or password is incorrect, or the account is inactive.')
    set_session(response, user)
    return user_json(user)

@app.post('/api/auth/logout')
def logout(response: Response):
    response.delete_cookie('medai_session', path='/')
    return {'ok': True}

@app.get('/api/auth/me')
def me(user=Depends(current_user)):
    return user_json(user)

@app.get('/api/conversations')
def conversations(user=Depends(current_user), db=Depends(get_db)):
    return [{'id': c.id, 'title': c.title, 'created_at': c.created_at.isoformat()} for c in db.scalars(select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.id.desc()).limit(100))]

@app.post('/api/conversations', status_code=201)
def create_conversation(user=Depends(current_user), db=Depends(get_db)):
    limit(db, f'conversation:{user.id}', 20)
    conversation = Conversation(user_id=user.id)
    db.add(conversation)
    db.commit()
    return {'id': conversation.id, 'title': conversation.title}

@app.get('/api/conversations/{cid}/messages')
def messages(cid: int, user=Depends(current_user), db=Depends(get_db)):
    own_conversation(db, cid, user.id)
    return [message_json(m) for m in db.scalars(select(Message).where(Message.conversation_id == cid).order_by(Message.id).limit(200))]

@app.post('/api/conversations/{cid}/messages')
async def chat(cid: int, data: ChatInput, user=Depends(current_user), db=Depends(get_db)):
    conversation = own_conversation(db, cid, user.id)
    limit(db, f'chat:{user.id}', 12)
    total = db.scalar(select(func.count(Message.id)).where(Message.conversation_id == cid))
    if total >= 200:
        raise HTTPException(400, 'Please start a new conversation to continue.')
    history = list(db.scalars(select(Message).where(Message.conversation_id == cid).order_by(Message.id.desc()).limit(8)))[::-1]
    documents = list(db.scalars(select(Document).where(Document.approved.is_(True)).order_by(Document.id)))
    result = await answer(data.message, history, documents)
    if not history:
        conversation.title = data.message[:90]
    question = Message(conversation_id=cid, sender='user', content=data.message)
    reply = Message(conversation_id=cid, sender='assistant', content=result['content'], mode=result['mode'], sources_json=json.dumps(result['sources']))
    db.add_all([question, reply])
    db.commit()
    return {'question': message_json(question), 'reply': message_json(reply)}

@app.delete('/api/conversations/{cid}')
def delete_conversation(cid: int, user=Depends(current_user), db=Depends(get_db)):
    conversation = own_conversation(db, cid, user.id)
    ids = select(Message.id).where(Message.conversation_id == cid)
    db.execute(delete(Feedback).where(Feedback.message_id.in_(ids)))
    db.execute(delete(Message).where(Message.conversation_id == cid))
    db.delete(conversation)
    db.commit()
    return {'ok': True}

@app.post('/api/feedback', status_code=201)
def feedback(data: FeedbackInput, user=Depends(current_user), db=Depends(get_db)):
    message = db.get(Message, data.message_id)
    if not message or message.sender != 'assistant':
        raise HTTPException(404, 'Reply not found.')
    own_conversation(db, message.conversation_id, user.id)
    existing = db.scalar(select(Feedback).where(Feedback.user_id == user.id, Feedback.message_id == data.message_id))
    if existing:
        existing.rating, existing.comments = data.rating, data.comments
    else:
        db.add(Feedback(user_id=user.id, **data.model_dump()))
    db.commit()
    return {'ok': True}

@app.get('/api/library')
def library(db=Depends(get_db)):
    return [doc_json(d) for d in db.scalars(select(Document).where(Document.approved.is_(True)).order_by(Document.title))]

@app.get('/api/admin/documents')
def admin_documents(user=Depends(admin_user), db=Depends(get_db)):
    return [doc_json(d) for d in db.scalars(select(Document).order_by(Document.id.desc()))]

@app.post('/api/admin/documents', status_code=201)
def add_document(data: DocumentInput, user=Depends(admin_user), db=Depends(get_db)):
    doc = Document(**data.model_dump(), uploaded_by=user.id, reviewed_at=now() if data.approved else None)
    db.add(doc)
    db.flush()
    db.add(Audit(user_id=user.id, action=f'Created document {doc.id}; approved={data.approved}'))
    db.commit()
    return doc_json(doc)

@app.put('/api/admin/documents/{did}')
def edit_document(did: int, data: DocumentInput, user=Depends(admin_user), db=Depends(get_db)):
    doc = db.get(Document, did)
    if not doc:
        raise HTTPException(404, 'Document not found.')
    for key, value in data.model_dump().items():
        setattr(doc, key, value)
    doc.reviewed_at = now() if data.approved else None
    db.add(Audit(user_id=user.id, action=f'Updated document {did}; approved={data.approved}'))
    db.commit()
    return doc_json(doc)

@app.delete('/api/admin/documents/{did}')
def remove_document(did: int, user=Depends(admin_user), db=Depends(get_db)):
    doc = db.get(Document, did)
    if not doc:
        raise HTTPException(404, 'Document not found.')
    db.delete(doc)
    db.add(Audit(user_id=user.id, action=f'Deleted document {did}'))
    db.commit()
    return {'ok': True}

@app.get('/api/admin/users')
def users(user=Depends(admin_user), db=Depends(get_db)):
    return [user_json(u) for u in db.scalars(select(User).order_by(User.id.desc()).limit(200))]

@app.patch('/api/admin/users/{uid}')
def update_user(uid: int, data: UserUpdate, user=Depends(admin_user), db=Depends(get_db)):
    target = db.get(User, uid)
    if not target:
        raise HTTPException(404, 'User not found.')
    if target.role == 'admin':
        raise HTTPException(400, 'Administrator accounts cannot be disabled here.')
    target.active = data.active
    db.add(Audit(user_id=user.id, action=f'User {uid} active={data.active}'))
    db.commit()
    return user_json(target)

@app.get('/api/admin/reports')
def reports(user=Depends(admin_user), db=Depends(get_db)):
    count = lambda cls: db.scalar(select(func.count(cls.id)))
    daily = db.execute(select(func.date(Message.created_at), func.count(Message.id)).where(Message.sender == 'user').group_by(func.date(Message.created_at)).order_by(func.date(Message.created_at).desc()).limit(14)).all()
    frequent = db.execute(select(Message.content, func.count(Message.id).label('n')).where(Message.sender == 'user').group_by(Message.content).order_by(func.count(Message.id).desc()).limit(10)).all()
    db.add(Audit(user_id=user.id, action='Viewed usage reports and frequent questions'))
    db.commit()
    return {'users': count(User), 'conversations': count(Conversation), 'documents': count(Document), 'approved_documents': db.scalar(select(func.count(Document.id)).where(Document.approved.is_(True))), 'messages': count(Message), 'feedback_count': count(Feedback), 'average_rating': db.scalar(select(func.avg(Feedback.rating))), 'emergencies': db.scalar(select(func.count(Message.id)).where(Message.mode == 'emergency')), 'daily': [{'date': str(d), 'questions': n} for d, n in reversed(daily)], 'frequent_questions': [{'question': q, 'count': n} for q, n in frequent]}

@app.get('/api/admin/interactions')
def interactions(user=Depends(admin_user), db=Depends(get_db)):
    db.add(Audit(user_id=user.id, action='Viewed recent chatbot interactions'))
    db.commit()
    return [message_json(m) | {'conversation_id': m.conversation_id} for m in db.scalars(select(Message).order_by(Message.id.desc()).limit(100))]

@app.get('/api/admin/audit')
def audit(user=Depends(admin_user), db=Depends(get_db)):
    return [{'user_id': a.user_id, 'action': a.action, 'created_at': a.created_at.isoformat()} for a in db.scalars(select(Audit).order_by(Audit.id.desc()).limit(100))]

ROOT = Path(__file__).resolve().parent.parent
app.mount('/static', StaticFiles(directory=ROOT / 'frontend'), name='static')

@app.get('/')
def index():
    return FileResponse(ROOT / 'frontend' / 'index.html')
