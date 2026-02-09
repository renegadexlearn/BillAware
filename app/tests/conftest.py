import pytest
from app import create_app
from app.extensions import db as _db

@pytest.fixture()
def app(tmp_path):
    db_path = tmp_path / "test_qfleet.sqlite"

    app = create_app()
    app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{db_path}",
        SQLALCHEMY_ENGINE_OPTIONS={
            "connect_args": {"check_same_thread": False},
        },
    )

    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()

@pytest.fixture()
def client(app):
    return app.test_client()

@pytest.fixture()
def db(app):
    return _db
