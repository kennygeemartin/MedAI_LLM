"""Create a random-password local administrator and import draft articles."""
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from sqlalchemy import select
from backend.database import PRODUCTION, Base, engine, Session, User
from backend.security import hash_password
from backend.seed import main as seed

if PRODUCTION or engine.dialect.name != 'sqlite':
    raise SystemExit('Local bootstrap requires a development SQLite database.')
Base.metadata.create_all(engine)
with Session() as db:
    admin = db.scalar(select(User).where(User.role == 'admin'))
    if admin:
        print('An administrator already exists; credentials were not changed.')
    else:
        password = secrets.token_urlsafe(24)
        email = 'admin@medai.local'
        db.add(User(email=email, full_name='MedAI Administrator', password_hash=hash_password(password), role='admin'))
        db.commit()
        directory = ROOT / 'artifacts'
        directory.mkdir(exist_ok=True)
        (directory / 'local-admin.txt').write_text(f'LOCAL DEVELOPMENT ONLY\nURL: http://127.0.0.1:8000\nEmail: {email}\nPassword: {password}\n\nKeep this file private. It is excluded from Git and deployment packages.\n', encoding='utf-8')
        print('Generated local login details in artifacts/local-admin.txt (excluded from Git).')
seed()
