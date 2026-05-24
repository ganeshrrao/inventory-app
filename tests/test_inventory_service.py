"""
tests/test_inventory_service.py - Unit tests for InventoryService
"""
import pytest
from unittest.mock import AsyncMock

from models.inventory import Category, Receipt, ReceiptLineItem, ProcessingStatus
from services.inventory_service import InventoryService


# ── Item CRUD ────────────────────────────────────────────────────────────────

def test_create_item(svc):
    item = svc.create_item({"name": "Drill Bit", "quantity": 10, "unit_price": 9.99})
    assert item.name == "Drill Bit"
    assert item.quantity == 10


def test_create_item_defaults(svc):
    item = svc.create_item({"name": "Screw"})
    assert item.quantity == 0
    assert item.low_stock_threshold == 5


def test_get_item(svc):
    item = svc.create_item({"name": "Widget", "quantity": 3})
    assert svc.get_item(item.id).id == item.id


def test_get_item_not_found(svc):
    assert svc.get_item("nonexistent-id") is None


def test_update_item(svc):
    item = svc.create_item({"name": "Bolt", "quantity": 5})
    updated = svc.update_item(item.id, {"name": "Hex Bolt", "quantity": 20})
    assert updated.name == "Hex Bolt"
    assert updated.quantity == 20


def test_update_item_not_found(svc):
    assert svc.update_item("nonexistent-id", {"name": "Ghost"}) is None


def test_low_stock_flag(svc):
    item = svc.create_item({"name": "Screw", "quantity": 2, "low_stock_threshold": 5})
    assert item.is_low_stock is True


def test_not_low_stock(svc):
    item = svc.create_item({"name": "Bolt", "quantity": 10, "low_stock_threshold": 5})
    assert item.is_low_stock is False


def test_adjust_quantity(svc):
    item = svc.create_item({"name": "Bolt", "quantity": 10})
    updated = svc.adjust_quantity(item.id, -3)
    assert updated.quantity == 7


def test_adjust_quantity_floor_at_zero(svc):
    item = svc.create_item({"name": "Bolt", "quantity": 10})
    svc.adjust_quantity(item.id, -100)
    assert svc.get_item(item.id).quantity == 0


def test_adjust_quantity_not_found(svc):
    assert svc.adjust_quantity("nonexistent-id", -1) is None


def test_delete_item(svc):
    item = svc.create_item({"name": "Widget", "quantity": 5})
    assert svc.delete_item(item.id) is True
    assert svc.get_item(item.id) is None


def test_delete_item_not_found(svc):
    assert svc.delete_item("nonexistent-id") is False


# ── Filtering & pagination ────────────────────────────────────────────────────

def test_search_by_name(svc):
    svc.create_item({"name": "Milwaukee Drill", "sku": "2804-20", "quantity": 3})
    svc.create_item({"name": "DeWalt Saw", "sku": "DCS391B", "quantity": 5})
    result = svc.get_all_items(search="Milwaukee")
    assert result["total"] == 1
    assert result["items"][0]["name"] == "Milwaukee Drill"


def test_search_by_sku(svc):
    svc.create_item({"name": "Drill", "sku": "UNIQUE-SKU-XYZ", "quantity": 1})
    assert svc.get_all_items(search="UNIQUE-SKU-XYZ")["total"] == 1


def test_filter_by_category(db, svc):
    cat = Category(name="Power Tools Filter Test")
    db.add(cat)
    db.commit()
    svc.create_item({"name": "Cat Filter Drill", "quantity": 1, "category_id": cat.id})
    svc.create_item({"name": "No Cat Item", "quantity": 1})
    result = svc.get_all_items(category_id=cat.id)
    assert result["total"] == 1
    assert result["items"][0]["name"] == "Cat Filter Drill"


def test_filter_low_stock_only(svc):
    svc.create_item({"name": "LS-Low999",  "quantity": 1,  "low_stock_threshold": 5})
    svc.create_item({"name": "LS-OK999",   "quantity": 20, "low_stock_threshold": 5})
    result = svc.get_all_items(low_stock_only=True, search="LS-")
    assert result["total"] == 1
    assert "LS-Low" in result["items"][0]["name"]


def test_pagination(svc):
    for i in range(5):
        svc.create_item({"name": f"PageItem{i}", "quantity": i})
    page1 = svc.get_all_items(search="PageItem", skip=0, limit=2)
    page2 = svc.get_all_items(search="PageItem", skip=2, limit=2)
    assert page1["total"] == 5
    assert len(page1["items"]) == 2
    assert len(page2["items"]) == 2


# ── Summary ───────────────────────────────────────────────────────────────────

def test_get_summary(db, svc):
    cat = Category(name="SummaryTestCat")
    db.add(cat)
    db.commit()
    svc.create_item({"name": "SumA", "quantity": 4, "unit_price": 10.0,
                     "category_id": cat.id, "low_stock_threshold": 10})
    svc.create_item({"name": "SumB", "quantity": 50, "unit_price": 1.0})
    summary = svc.get_summary()
    assert summary["total_items"] >= 2
    assert summary["total_value"] >= 4 * 10.0 + 50 * 1.0
    assert summary["low_stock_count"] >= 1   # SumA (qty 4 ≤ threshold 10) is low
    assert summary["category_count"] >= 1


# ── Receipt deduplication ─────────────────────────────────────────────────────

def _receipt(db):
    r = Receipt(image_path="test.jpg", status=ProcessingStatus.COMPLETED)
    db.add(r)
    db.commit()
    return r


def test_receipt_creates_new_item(db, svc):
    r = _receipt(db)
    li = ReceiptLineItem(receipt_id=r.id, name="UniqueWrench9911", quantity=2, unit_price=15.0)
    db.add(li); db.commit()
    items = svc.create_items_from_receipt(r.id, [li.id])
    assert len(items) == 1
    assert items[0].name == "UniqueWrench9911"
    assert items[0].quantity == 2


def test_receipt_dedup_by_sku(db, svc):
    existing = svc.create_item({"name": "DedupBolt", "sku": "DEDUP-SKU-001", "quantity": 5})
    r = _receipt(db)
    li = ReceiptLineItem(receipt_id=r.id, name="Bolt (receipt name)", parsed_sku="DEDUP-SKU-001", quantity=3)
    db.add(li); db.commit()
    svc.create_items_from_receipt(r.id, [li.id])
    db.refresh(existing)
    assert existing.quantity == 8  # 5 + 3


def test_receipt_dedup_by_name(db, svc):
    existing = svc.create_item({"name": "DedupHammer", "quantity": 2})
    r = _receipt(db)
    li = ReceiptLineItem(receipt_id=r.id, name="DEDUPHAMMER", quantity=1)  # case-insensitive
    db.add(li); db.commit()
    svc.create_items_from_receipt(r.id, [li.id])
    db.refresh(existing)
    assert existing.quantity == 3  # 2 + 1


def test_receipt_new_item_when_no_match(db, svc):
    before = svc.get_all_items()["total"]
    r = _receipt(db)
    li = ReceiptLineItem(receipt_id=r.id, name="TotallyNewReceiptItem777", quantity=1)
    db.add(li); db.commit()
    items = svc.create_items_from_receipt(r.id, [li.id])
    assert len(items) == 1
    assert svc.get_all_items()["total"] == before + 1


# ── Vendor enrichment ─────────────────────────────────────────────────────────

async def test_vendor_enrichment(db):
    from vendors.base import ProductInfo
    mock = AsyncMock()
    mock.lookup_sku.return_value = ProductInfo(sku="123", name="Test Drill", price=149.99, description="A drill")
    svc = InventoryService(db=db, vendor_adapter=mock)
    data = await svc.enrich_from_vendor("123")
    assert data["name"] == "Test Drill"
    assert data["unit_price"] == 149.99
    mock.lookup_sku.assert_called_once_with("123")


async def test_vendor_enrichment_no_adapter(db):
    svc = InventoryService(db=db)
    with pytest.raises(RuntimeError, match="No vendor adapter"):
        await svc.enrich_from_vendor("123")


async def test_vendor_enrichment_not_found(db):
    mock = AsyncMock()
    mock.lookup_sku.return_value = None
    svc = InventoryService(db=db, vendor_adapter=mock)
    assert await svc.enrich_from_vendor("NOTFOUND") is None
