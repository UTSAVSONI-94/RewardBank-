import os
import sys

# Ensure root directory is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient

from app.db import get_db, init_schema, reset_db, seed_data
from app.main import create_app

PARENT_TOKEN = "parent-token-alice"
CHILD_TOKEN = "child-token-bob"
CHILD2_TOKEN = "child-token-charlie"


@pytest.fixture(autouse=True)
def setup_test_db():
    """Reset database to fresh state before each test."""
    reset_db()
    db = get_db()
    init_schema(db)
    seed_data(db)
    yield
    reset_db()


@pytest.fixture
def client():
    """Test client for FastAPI app."""
    app = create_app()
    with TestClient(app) as c:
        yield c
