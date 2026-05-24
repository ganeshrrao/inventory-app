"""
models/inventory.py - SQLAlchemy ORM Models
"""
import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, String, Integer, Numeric, Boolean, Text, 
    DateTime, ForeignKey, Enum, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, DeclarativeBase


class Base(DeclarativeBase):
    pass


class ProcessingStatus(str, PyEnum):
    PENDING   = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED    = "failed"


class VendorType(str, PyEnum):
    HOME_DEPOT = "home_depot"
    AMAZON     = "amazon"
    LOWES      = "lowes"
    CUSTOM     = "custom"


def new_uuid() -> str:
    return str(uuid.uuid4())


# ─────────────────────────────────────────────────────────────────────────────
class Category(Base):
    __tablename__ = "categories"

    id          = Column(String(36), primary_key=True, default=new_uuid)
    name        = Column(String(120), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    parent_id   = Column(String(36), ForeignKey("categories.id"), nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow)

    children    = relationship("Category", backref="parent", remote_side=[id])
    items       = relationship("InventoryItem", back_populates="category")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "parent_id": self.parent_id,
            "item_count": len(self.items),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ─────────────────────────────────────────────────────────────────────────────
class Vendor(Base):
    __tablename__ = "vendors"

    id           = Column(String(36), primary_key=True, default=new_uuid)
    name         = Column(String(120), nullable=False)
    vendor_type  = Column(Enum(VendorType), nullable=False)
    api_endpoint = Column(String(255), nullable=True)
    api_key      = Column(String(255), nullable=True)   # encrypted at rest in prod
    contact_info = Column(JSON, nullable=True)
    active       = Column(Boolean, default=True)
    created_at   = Column(DateTime, default=datetime.utcnow)

    items    = relationship("InventoryItem", back_populates="vendor")
    receipts = relationship("Receipt", back_populates="vendor")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "vendor_type": self.vendor_type,
            "active": self.active,
        }


# ─────────────────────────────────────────────────────────────────────────────
class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id                  = Column(String(36), primary_key=True, default=new_uuid)
    sku                 = Column(String(80), nullable=True, index=True)
    name                = Column(String(255), nullable=False)
    description         = Column(Text, nullable=True)
    quantity            = Column(Integer, default=0, nullable=False)
    unit_price          = Column(Numeric(10, 2), nullable=True)
    category_id         = Column(String(36), ForeignKey("categories.id"), nullable=True)
    vendor_id           = Column(String(36), ForeignKey("vendors.id"), nullable=True)
    low_stock_threshold  = Column(Integer, default=5)
    image_url            = Column(String(512), nullable=True)
    meta                 = Column(JSON, nullable=True)   # vendor-specific extra fields
    created_by_email     = Column(String(255), nullable=True)  # who added this item
    created_at           = Column(DateTime, default=datetime.utcnow)
    updated_at           = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    category  = relationship("Category", back_populates="items")
    vendor    = relationship("Vendor", back_populates="items")

    @property
    def is_low_stock(self) -> bool:
        return self.quantity <= self.low_stock_threshold

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "sku": self.sku,
            "name": self.name,
            "description": self.description,
            "quantity": self.quantity,
            "unit_price": float(self.unit_price) if self.unit_price else None,
            "category": self.category.to_dict() if self.category else None,
            "vendor": self.vendor.to_dict() if self.vendor else None,
            "low_stock_threshold": self.low_stock_threshold,
            "is_low_stock": self.is_low_stock,
            "image_url": self.image_url,
            "meta": self.meta,
            "created_by_email": self.created_by_email,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ─────────────────────────────────────────────────────────────────────────────
class Receipt(Base):
    __tablename__ = "receipts"

    id            = Column(String(36), primary_key=True, default=new_uuid)
    image_path    = Column(String(512), nullable=False)
    vendor_id     = Column(String(36), ForeignKey("vendors.id"), nullable=True)
    purchase_date = Column(DateTime, nullable=True)
    total_amount  = Column(Numeric(10, 2), nullable=True)
    status        = Column(Enum(ProcessingStatus), default=ProcessingStatus.PENDING)
    raw_ocr_text  = Column(Text, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)

    vendor     = relationship("Vendor", back_populates="receipts")
    line_items = relationship("ReceiptLineItem", back_populates="receipt", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "image_path": self.image_path,
            "vendor": self.vendor.to_dict() if self.vendor else None,
            "purchase_date": self.purchase_date.isoformat() if self.purchase_date else None,
            "total_amount": float(self.total_amount) if self.total_amount else None,
            "status": self.status,
            "line_items": [li.to_dict() for li in self.line_items],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ─────────────────────────────────────────────────────────────────────────────
class ReceiptLineItem(Base):
    __tablename__ = "receipt_line_items"

    id              = Column(String(36), primary_key=True, default=new_uuid)
    receipt_id      = Column(String(36), ForeignKey("receipts.id"), nullable=False)
    raw_text        = Column(String(500), nullable=True)
    parsed_sku      = Column(String(80), nullable=True)
    name            = Column(String(255), nullable=True)
    quantity        = Column(Integer, default=1)
    unit_price      = Column(Numeric(10, 2), nullable=True)
    matched_item_id = Column(String(36), ForeignKey("inventory_items.id"), nullable=True)

    receipt      = relationship("Receipt", back_populates="line_items")
    matched_item = relationship("InventoryItem")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "raw_text": self.raw_text,
            "parsed_sku": self.parsed_sku,
            "name": self.name,
            "quantity": self.quantity,
            "unit_price": float(self.unit_price) if self.unit_price else None,
            "matched_item_id": self.matched_item_id,
        }


# ─────────────────────────────────────────────────────────────────────────────
class ItemHistory(Base):
    """Append-only audit log for inventory item changes."""
    __tablename__ = "item_history"

    id         = Column(String(36), primary_key=True, default=new_uuid)
    # Nullable so history survives item deletion (no FK cascade needed).
    item_id    = Column(String(36), ForeignKey("inventory_items.id", ondelete="SET NULL"), nullable=True)
    item_name  = Column(String(255), nullable=False)  # denormalized — readable after deletion
    action     = Column(String(50), nullable=False)   # created | updated | deleted | quantity_adjusted
    changes    = Column(JSON, nullable=True)           # field-level diff: {field: {old, new}}
    user_id    = Column(String(36), nullable=True)
    user_email = Column(String(255), nullable=True)   # denormalized — readable after user deletion
    created_at = Column(DateTime, default=datetime.utcnow)

    item = relationship("InventoryItem", foreign_keys=[item_id])

    def to_dict(self) -> dict:
        return {
            "id":         self.id,
            "item_id":    self.item_id,
            "item_name":  self.item_name,
            "action":     self.action,
            "changes":    self.changes,
            "user_id":    self.user_id,
            "user_email": self.user_email,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
