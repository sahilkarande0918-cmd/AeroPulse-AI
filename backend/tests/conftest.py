import shutil

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base, get_db, make_engine
from app.main import app

PASSWORD = "test-demo-pass"


@pytest.fixture(scope="session")
def template_db(tmp_path_factory):
    """Seed once; each test gets a fresh copy of the file."""
    from app import seed as seed_mod
    settings.demo_password = PASSWORD
    path = tmp_path_factory.mktemp("db") / "template.db"
    eng = make_engine(f"sqlite:///{path.as_posix()}")
    Base.metadata.create_all(eng)
    with sessionmaker(bind=eng)() as s:
        seed_mod.seed(s)
    eng.dispose()
    return path


@pytest.fixture
def db_url(template_db, tmp_path):
    p = tmp_path / "t.db"
    shutil.copy(template_db, p)
    return f"sqlite:///{p.as_posix()}"


@pytest.fixture
def Session(db_url):
    eng = make_engine(db_url)
    yield sessionmaker(bind=eng, expire_on_commit=False)
    eng.dispose()


@pytest.fixture
def db(Session):
    with Session() as s:
        yield s


@pytest.fixture
def client(Session):
    def override():
        s = Session()
        try:
            yield s
        finally:
            s.close()
    app.dependency_overrides[get_db] = override
    from app.security import _attempts
    _attempts.clear()
    yield TestClient(app)
    app.dependency_overrides.clear()


def auth(client, user):
    r = client.post("/api/auth/login", json={"username": user, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
