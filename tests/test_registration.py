import pytest
from sqlalchemy import select, create_engine, text, inspect
from backend.database import User, UserProfile, ensure_profile_table
from tests.test_app import clients, PASSWORD, HEADERS

def payload(**changes):
    return dict(full_name='  Ada Example  ', gender='Female', age=32,
                phone_number='+234 801-234-5678', email='ada@example.com',
                username='Ada_Example', password=PASSWORD, consent=True) | changes

def test_profile_persisted_and_existing_login_preserved(clients):
    client, _, session = clients
    result = client.post('/api/auth/register', json=payload())
    assert result.status_code == 201, result.text
    with session() as db:
        user = db.get(User, result.json()['id'])
        assert user.full_name == 'Ada Example'
        assert user.password_hash != PASSWORD
        profile = db.get(UserProfile, user.id)
        assert (profile.gender, profile.age, profile.phone_number, profile.username) == (
            'Female', 32, '+2348012345678', 'ada_example')
    client.post('/api/auth/logout')
    assert client.post('/api/auth/login', json={'email':'ada@example.com','password':PASSWORD}).status_code == 200

def test_duplicate_username_is_case_insensitive_and_atomic(clients):
    client, _, session = clients
    assert client.post('/api/auth/register', json=payload()).status_code == 201
    assert client.post('/api/auth/register', json=payload(email='second@example.com', username='ADA_EXAMPLE')).status_code == 409
    with session() as db:
        assert db.scalar(select(User).where(User.email == 'second@example.com')) is None

@pytest.mark.parametrize('field,value', [
    ('full_name','  '), ('gender',''), ('age',0), ('age',121), ('age',2.5),
    ('phone_number','invalid'), ('phone_number','123456'),
    ('username','bad name'), ('username','ab'),
])
def test_invalid_profile_rejected(clients, field, value):
    client, _, _ = clients
    assert client.post('/api/auth/register', json=payload(**{field:value})).status_code == 422

@pytest.mark.parametrize('field', ['gender','age','phone_number','username'])
def test_profile_fields_required(clients, field):
    client, _, _ = clients
    data = payload()
    del data[field]
    assert client.post('/api/auth/register', json=data).status_code == 422

def test_additive_profile_table_preserves_existing_users(tmp_path, monkeypatch):
    import backend.database as database
    engine = create_engine('sqlite:///' + str(tmp_path / 'legacy.db'))
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE users (id INTEGER PRIMARY KEY, full_name VARCHAR(100), email VARCHAR(254), password_hash VARCHAR(255), role VARCHAR(20), active BOOLEAN, created_at DATETIME)'))
        conn.execute(text("INSERT INTO users VALUES (1, 'Existing User', 'old@example.com', 'existing-hash', 'patient', 1, '2026-01-01')"))
    monkeypatch.setattr(database, 'engine', engine)
    ensure_profile_table()
    ensure_profile_table()
    with engine.connect() as conn:
        assert conn.execute(text('SELECT email, password_hash FROM users WHERE id=1')).one() == ('old@example.com', 'existing-hash')
    assert 'user_profiles' in inspect(engine).get_table_names()
    engine.dispose()
