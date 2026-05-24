"""
tests/conftest.py - Shared fixtures and path setup for all tests.

Backend code uses unqualified imports (e.g. `from models.inventory import ...`)
that only work when backend/ is on sys.path, so we add it here before any
test module is imported.
"""
import sys
import os

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.inventory import Base
import models.user  # noqa: F401 — registers User table with Base.metadata


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def svc(db):
    from services.inventory_service import InventoryService
    return InventoryService(db=db)
