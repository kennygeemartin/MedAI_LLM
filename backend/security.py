import hashlib
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select, update, delete
from sqlalchemy.exc import IntegrityError
from backend.database import PRODUCTION, RateBucket, User, get_db

SECRET = os.getenv('JWT_SECRET', '')
if len(SECRET) < 32:
    if PRODUCTION:
        raise RuntimeError('Set JWT_SECRET to a random secret of at least 32 characters.')
    SECRET = secrets.token_urlsafe(48)
DUMMY_HASH = bcrypt.hashpw(b'dummy-password', bcrypt.gensalt()).decode()

def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password, encoded):
    return bcrypt.checkpw(password.encode(), encoded.encode())

def token_for(user):
    return jwt.encode({'sub': str(user.id), 'exp': datetime.now(timezone.utc) + timedelta(hours=8), 'iat': datetime.now(timezone.utc)}, SECRET, algorithm='HS256')

def current_user(request: Request, db=Depends(get_db)):
    try:
        payload = jwt.decode(request.cookies.get('medai_session', ''), SECRET, algorithms=['HS256'])
        user = db.get(User, int(payload['sub']))
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(401, 'Please sign in to continue.')
    if not user or not user.active:
        raise HTTPException(401, 'Your session is unavailable. Please sign in again.')
    return user

def admin_user(user=Depends(current_user)):
    if user.role != 'admin':
        raise HTTPException(403, 'Administrator access is required.')
    return user

def limit(db, identity, limit_count, seconds=60):
    # Atomic counters in the shared database also work across serverless instances.
    window = int(time.time()) // seconds
    key = f'{window:012d}:' + hashlib.sha256(identity.encode()).hexdigest()
    if not db.get(RateBucket, key):
        try:
            with db.begin_nested():
                db.add(RateBucket(key=key, count=0))
                db.flush()
        except IntegrityError:
            pass
    count = db.execute(update(RateBucket).where(RateBucket.key == key).values(count=RateBucket.count + 1).returning(RateBucket.count)).scalar_one()
    db.execute(delete(RateBucket).where(RateBucket.key < f'{window - 2:012d}:'))
    db.commit()
    if count > limit_count:
        raise HTTPException(429, 'Too many requests. Please wait a minute and try again.')
