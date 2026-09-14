"""Explicit database setup and administrator creation; no default passwords."""
import argparse
import getpass
from sqlalchemy import select
from backend.database import Base, engine, Session, User
from backend.security import hash_password
from backend.main import Credentials

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['init-db', 'create-admin'])
    args = parser.parse_args()
    Base.metadata.create_all(engine)
    if args.command == 'init-db':
        print('Database tables initialized.')
        return
    email = input('Administrator email: ').strip().lower()
    name = input('Full name: ').strip()
    password = getpass.getpass('Password (10–72 bytes): ')
    Credentials(email=email, password=password)
    if len(name) < 2:
        raise SystemExit('A full name is required.')
    if password != getpass.getpass('Confirm password: '):
        raise SystemExit('Passwords do not match.')
    with Session() as db:
        if db.scalar(select(User).where(User.email == email)):
            raise SystemExit('Account already exists; no role was changed.')
        db.add(User(email=email, full_name=name, password_hash=hash_password(password), role='admin'))
        db.commit()
    print('Administrator created.')

if __name__ == '__main__':
    main()
