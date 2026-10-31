import pytest
from backend.database import init_db

@pytest.fixture(autouse=True, scope="session")
def setup_test_db():
    init_db()

