import pytest

from app import create_app
from app.db import get_db, init_db, seed_db


@pytest.fixture
def app(tmp_path):
    app = create_app({"TESTING": True, "TESTING_SIN_CSRF": True,
                      "DATABASE": str(tmp_path / "t.db"), "SELLO_SECRET": "secreto-de-prueba",
                      "SECRET_KEY": "x", "BASE_URL": "http://prueba.local"})
    with app.app_context():
        init_db()
        seed_db()
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def entrar(client, email):
    return client.post("/login", data={"email": email, "password": "demo1234"}, follow_redirects=True)


@pytest.fixture
def db(app):
    with app.app_context():
        yield get_db()
