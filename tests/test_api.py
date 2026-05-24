"""
tests/test_api.py - FastAPI integration tests.

Uses TestClient with dependency overrides for DB and auth so tests run
without a real database file or valid JWT tokens.
"""
import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("SECRET_KEY", "test-secret-key-pytest")

from database import get_db                   # noqa: E402
from dependencies import get_current_user     # noqa: E402
from models.inventory import Base             # noqa: E402
import models.user                            # noqa: F401,E402 — registers User
from models.user import User                  # noqa: E402

# StaticPool keeps every checkout on the same underlying connection so the
# in-memory database isn't reset between the create_all() call and test requests.
_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(_engine)
_Session = sessionmaker(bind=_engine, autocommit=False, autoflush=False)


def _db():
    db = _Session()
    try:
        yield db
    finally:
        db.close()


def _user():
    return User(id="test-user", email="t@t.com", hashed_password="x", is_active=True)


@pytest.fixture(scope="module")
def client():
    # Patch out Alembic so the lifespan doesn't try to open alembic.ini
    with patch("main.AlembicConfig"), patch("main.alembic_command"):
        from main import app
        app.dependency_overrides[get_db] = _db
        app.dependency_overrides[get_current_user] = _user
        with TestClient(app) as c:
            yield c
        app.dependency_overrides.clear()


# ── Items ─────────────────────────────────────────────────────────────────────

def test_create_item(client):
    res = client.post("/api/items", json={"name": "API Test Drill", "quantity": 5, "unit_price": 29.99})
    assert res.status_code == 201
    d = res.json()
    assert d["name"] == "API Test Drill"
    assert d["quantity"] == 5
    assert d["id"]


def test_get_item(client):
    item_id = client.post("/api/items", json={"name": "Get Test Item", "quantity": 1}).json()["id"]
    res = client.get(f"/api/items/{item_id}")
    assert res.status_code == 200
    assert res.json()["id"] == item_id


def test_get_item_not_found(client):
    assert client.get("/api/items/nonexistent-id").status_code == 404


def test_list_items(client):
    res = client.get("/api/items")
    assert res.status_code == 200
    body = res.json()
    assert "items" in body and "total" in body


def test_list_items_search(client):
    client.post("/api/items", json={"name": "UniqueSearchItemXYZ", "quantity": 1})
    res = client.get("/api/items?search=UniqueSearchItemXYZ")
    assert res.status_code == 200
    assert res.json()["total"] >= 1


def test_list_items_low_stock_filter(client):
    client.post("/api/items", json={"name": "LowStockAPI999", "quantity": 1, "low_stock_threshold": 10})
    res = client.get("/api/items?low_stock_only=true&search=LowStockAPI999")
    assert res.status_code == 200
    assert res.json()["total"] == 1


def test_update_item(client):
    item_id = client.post("/api/items", json={"name": "Before Update", "quantity": 1}).json()["id"]
    res = client.patch(f"/api/items/{item_id}", json={"name": "After Update", "quantity": 99})
    assert res.status_code == 200
    assert res.json()["name"] == "After Update"
    assert res.json()["quantity"] == 99


def test_update_item_not_found(client):
    assert client.patch("/api/items/nonexistent", json={"name": "X"}).status_code == 404


def test_delete_item(client):
    item_id = client.post("/api/items", json={"name": "To Delete API", "quantity": 1}).json()["id"]
    assert client.delete(f"/api/items/{item_id}").status_code == 204
    assert client.get(f"/api/items/{item_id}").status_code == 404


def test_delete_item_not_found(client):
    assert client.delete("/api/items/nonexistent").status_code == 404


def test_adjust_quantity(client):
    item_id = client.post("/api/items", json={"name": "AdjQty Item", "quantity": 10}).json()["id"]
    res = client.post(f"/api/items/{item_id}/adjust-quantity", json={"delta": -3})
    assert res.status_code == 200
    assert res.json()["quantity"] == 7


def test_adjust_quantity_floor_zero(client):
    item_id = client.post("/api/items", json={"name": "FloorItem", "quantity": 5}).json()["id"]
    res = client.post(f"/api/items/{item_id}/adjust-quantity", json={"delta": -100})
    assert res.json()["quantity"] == 0


# ── Bulk operations ───────────────────────────────────────────────────────────

def test_bulk_delete(client):
    ids = [client.post("/api/items", json={"name": f"BulkDel{i}", "quantity": 1}).json()["id"] for i in range(3)]
    res = client.post("/api/items/bulk-delete", json={"ids": ids})
    assert res.status_code == 200
    assert res.json()["deleted"] == 3
    for id in ids:
        assert client.get(f"/api/items/{id}").status_code == 404


def test_bulk_adjust(client):
    ids = [client.post("/api/items", json={"name": f"BulkAdj{i}", "quantity": 10}).json()["id"] for i in range(2)]
    res = client.post("/api/items/bulk-adjust", json={"ids": ids, "delta": 5})
    assert res.status_code == 200
    assert res.json()["updated"] == 2
    for id in ids:
        assert client.get(f"/api/items/{id}").json()["quantity"] == 15


def test_bulk_category(client):
    cat_id = client.post("/api/categories", json={"name": "Bulk Cat API Test"}).json()["id"]
    ids = [client.post("/api/items", json={"name": f"BulkCat{i}", "quantity": 1}).json()["id"] for i in range(2)]
    res = client.post("/api/items/bulk-category", json={"ids": ids, "category_id": cat_id})
    assert res.status_code == 200
    assert res.json()["updated"] == 2
    for id in ids:
        assert client.get(f"/api/items/{id}").json()["category"]["id"] == cat_id


def test_bulk_category_clear(client):
    cat_id = client.post("/api/categories", json={"name": "Clear Cat Test"}).json()["id"]
    item_id = client.post("/api/items", json={"name": "ClearCatItem", "quantity": 1, "category_id": cat_id}).json()["id"]
    client.post("/api/items/bulk-category", json={"ids": [item_id], "category_id": None})
    assert client.get(f"/api/items/{item_id}").json()["category"] is None


# ── Categories ────────────────────────────────────────────────────────────────

def test_create_category(client):
    res = client.post("/api/categories", json={"name": "Hand Tools API"})
    assert res.status_code == 201
    assert res.json()["name"] == "Hand Tools API"
    assert res.json()["item_count"] == 0


def test_list_categories(client):
    res = client.get("/api/categories")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_seed_categories(client):
    res = client.post("/api/categories/seed")
    assert res.status_code == 201
    assert "created" in res.json()
    # Seeding again is idempotent — second call creates 0
    res2 = client.post("/api/categories/seed")
    assert res2.json()["created"] == 0


def test_update_category(client):
    cat_id = client.post("/api/categories", json={"name": "OldCatName"}).json()["id"]
    res = client.patch(f"/api/categories/{cat_id}", json={"name": "NewCatName"})
    assert res.status_code == 200
    assert res.json()["name"] == "NewCatName"


def test_delete_category_nullifies_items(client):
    cat_id = client.post("/api/categories", json={"name": "DeleteMeCat"}).json()["id"]
    item_id = client.post("/api/items", json={"name": "OwnedItem", "quantity": 1, "category_id": cat_id}).json()["id"]
    assert client.delete(f"/api/categories/{cat_id}").status_code == 204
    assert client.get(f"/api/items/{item_id}").json()["category"] is None


def test_delete_category_not_found(client):
    assert client.delete("/api/categories/nonexistent").status_code == 404


# ── Dashboard ─────────────────────────────────────────────────────────────────

def test_dashboard_summary(client):
    res = client.get("/api/dashboard/summary")
    assert res.status_code == 200
    d = res.json()
    for key in ("total_items", "total_value", "low_stock_count", "category_count"):
        assert key in d


# ── Auth ──────────────────────────────────────────────────────────────────────

def test_register(client):
    res = client.post("/api/auth/register", json={"email": "newuser@test.com", "password": "password123"})
    assert res.status_code == 201
    assert "access_token" in res.json()


def test_register_duplicate_email(client):
    client.post("/api/auth/register", json={"email": "dup@test.com", "password": "password123"})
    res = client.post("/api/auth/register", json={"email": "dup@test.com", "password": "password123"})
    assert res.status_code == 400


def test_register_short_password(client):
    res = client.post("/api/auth/register", json={"email": "short@test.com", "password": "abc"})
    assert res.status_code == 400


def test_login(client):
    client.post("/api/auth/register", json={"email": "loginuser@test.com", "password": "password123"})
    res = client.post("/api/auth/login", json={"email": "loginuser@test.com", "password": "password123"})
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_login_wrong_password(client):
    client.post("/api/auth/register", json={"email": "wrongpw@test.com", "password": "correct123"})
    res = client.post("/api/auth/login", json={"email": "wrongpw@test.com", "password": "wrong"})
    assert res.status_code == 401


def test_login_unknown_email(client):
    res = client.post("/api/auth/login", json={"email": "nobody@test.com", "password": "anything"})
    assert res.status_code == 401
