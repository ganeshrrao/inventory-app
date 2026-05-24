"""
services/inventory_service.py - Core business logic
"""
import logging
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session, selectinload

from models.inventory import (
    InventoryItem, Category, Vendor, Receipt,
    ReceiptLineItem, ProcessingStatus, ItemHistory
)
from utils.ocr_service import OCRService
from vendors.base import VendorAdapter

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class InventoryService:
    def __init__(
        self,
        db: Session,
        vendor_adapter: Optional[VendorAdapter] = None,
        ocr_service: Optional[OCRService] = None,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
    ):
        self.db         = db
        self.vendor     = vendor_adapter
        self.ocr        = ocr_service
        self.user_id    = user_id
        self.user_email = user_email

    def _log(self, item: InventoryItem, action: str, changes: Optional[dict] = None) -> None:
        self.db.add(ItemHistory(
            item_id    = item.id,
            item_name  = item.name,
            action     = action,
            changes    = changes,
            user_id    = self.user_id,
            user_email = self.user_email,
        ))

    # ── Items ────────────────────────────────────────────────────────────────

    def get_all_items(
        self,
        search: Optional[str] = None,
        category_id: Optional[str] = None,
        low_stock_only: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> dict:
        q = (
            self.db.query(InventoryItem)
            .options(selectinload(InventoryItem.category), selectinload(InventoryItem.vendor))
        )
        if search:
            q = q.filter(or_(
                InventoryItem.name.ilike(f"%{search}%"),
                InventoryItem.sku.ilike(f"%{search}%"),
                InventoryItem.description.ilike(f"%{search}%"),
            ))
        if category_id:
            q = q.filter(InventoryItem.category_id == category_id)
        if low_stock_only:
            q = q.filter(InventoryItem.quantity <= InventoryItem.low_stock_threshold)

        total = q.count()
        items = q.offset(skip).limit(limit).all()
        return {"total": total, "items": [i.to_dict() for i in items]}

    def get_item(self, item_id: str) -> Optional[InventoryItem]:
        return self.db.get(InventoryItem, item_id)

    def create_item(self, data: dict) -> InventoryItem:
        item = InventoryItem(**data)
        item.created_by_email = self.user_email
        self.db.add(item)
        self.db.flush()   # assigns item.id within the transaction before commit
        self._log(item, "created")
        self.db.commit()
        self.db.refresh(item)
        logger.info("Created item %r (id=%s, qty=%d)", item.name, item.id, item.quantity)
        return item

    def update_item(self, item_id: str, data: dict) -> Optional[InventoryItem]:
        item = self.get_item(item_id)
        if not item:
            return None
        changes = {}
        for k, v in data.items():
            if hasattr(item, k):
                old = getattr(item, k)
                if old != v:
                    changes[k] = {"old": str(old) if old is not None else None,
                                  "new": str(v)  if v  is not None else None}
                setattr(item, k, v)
        item.updated_at = datetime.utcnow()
        self._log(item, "updated", changes or None)
        self.db.commit()
        self.db.refresh(item)
        logger.info("Updated item %r (id=%s, fields=%s)", item.name, item.id, list(data.keys()))
        return item

    def delete_item(self, item_id: str) -> bool:
        item = self.get_item(item_id)
        if not item:
            return False
        logger.info("Deleted item %r (id=%s)", item.name, item.id)
        # Write history with item_id=None: the item is about to be deleted and
        # SQLite won't enforce the FK constraint, but item_name preserves the record.
        self.db.add(ItemHistory(
            item_id    = None,
            item_name  = item.name,
            action     = "deleted",
            user_id    = self.user_id,
            user_email = self.user_email,
        ))
        self.db.delete(item)
        self.db.commit()
        return True

    def adjust_quantity(self, item_id: str, delta: int) -> Optional[InventoryItem]:
        """Increment or decrement stock. Prevents negative quantity."""
        item = self.get_item(item_id)
        if not item:
            return None
        old_qty = item.quantity
        item.quantity = max(0, item.quantity + delta)
        item.updated_at = datetime.utcnow()
        self._log(item, "quantity_adjusted", {
            "quantity": {"old": old_qty, "new": item.quantity, "delta": delta}
        })
        self.db.commit()
        self.db.refresh(item)
        logger.info("Adjusted qty for %r: %d → %d (delta=%+d)", item.name, old_qty, item.quantity, delta)
        return item

    # ── SKU enrichment from vendor ────────────────────────────────────────────

    async def enrich_from_vendor(self, sku: str) -> Optional[dict]:
        """
        Query vendor API for a SKU and return normalized product data.
        Does NOT persist — caller decides what to save.
        """
        if not self.vendor:
            raise RuntimeError("No vendor adapter configured")
        product = await self.vendor.lookup_sku(sku)
        if not product:
            return None
        return {
            "sku":         product.sku,
            "name":        product.name,
            "description": product.description,
            "unit_price":  product.price,
            "image_url":   product.image_url,
            "meta":        product.raw,
        }

    # ── Receipt processing ────────────────────────────────────────────────────

    def save_receipt_image(self, file_data: bytes, filename: str) -> str:
        """Persist uploaded file, return relative path."""
        ext      = Path(filename).suffix or ".jpg"
        name     = f"{uuid.uuid4()}{ext}"
        dest     = UPLOAD_DIR / name
        dest.write_bytes(file_data)
        return str(dest)

    async def process_receipt(self, image_path: str, vendor_id: Optional[str] = None) -> Receipt:
        """
        Full receipt pipeline:
          1. OCR → extract text + line items
          2. Create Receipt record
          3. Optionally enrich each line item via vendor SKU lookup
          4. Return Receipt with line items
        """
        if not self.ocr:
            raise RuntimeError("No OCR service configured")

        logger.info("Processing receipt: %s", image_path)
        receipt = Receipt(
            image_path = image_path,
            vendor_id  = vendor_id,
            status     = ProcessingStatus.PROCESSING,
        )
        self.db.add(receipt)
        self.db.commit()

        try:
            parsed          = await self.ocr.parse_receipt(image_path)
            receipt.raw_ocr_text  = parsed.raw_text
            receipt.total_amount  = parsed.total_amount
            if parsed.purchase_date:
                try:
                    receipt.purchase_date = datetime.fromisoformat(parsed.purchase_date)
                except ValueError:
                    pass

            for li in parsed.line_items:
                matched_id = None
                if li.sku:
                    existing = self.db.query(InventoryItem).filter(InventoryItem.sku == li.sku).first()
                    if existing:
                        matched_id = existing.id

                line_item = ReceiptLineItem(
                    receipt_id      = receipt.id,
                    raw_text        = li.raw_text,
                    parsed_sku      = li.sku,
                    name            = li.name,
                    quantity        = li.quantity,
                    unit_price      = li.unit_price,
                    matched_item_id = matched_id,
                )
                self.db.add(line_item)

            receipt.status = ProcessingStatus.COMPLETED
            logger.info("Receipt %s processed: %d line items, total=%s", receipt.id, len(parsed.line_items), parsed.total_amount)

        except Exception as e:
            logger.exception("Receipt processing failed: %s", e)
            receipt.status    = ProcessingStatus.FAILED
            receipt.raw_ocr_text = f"ERROR: {e}"

        self.db.commit()
        self.db.refresh(receipt)
        return receipt

    def create_items_from_receipt(self, receipt_id: str, selected_line_item_ids: list[str]) -> list[InventoryItem]:
        """Convert selected receipt line items into inventory items.

        Deduplication priority:
          1. Exact SKU match
          2. Case-insensitive name match
          → Match found: increment quantity
          → No match: create new item
        """
        results = []
        n_created = n_updated = 0

        for li_id in selected_line_item_ids:
            li = self.db.get(ReceiptLineItem, li_id)
            if not li or not li.name:
                continue

            qty = li.quantity or 1

            # 1) Try SKU match
            existing = None
            if li.parsed_sku:
                existing = (
                    self.db.query(InventoryItem)
                    .filter(InventoryItem.sku == li.parsed_sku)
                    .first()
                )

            # 2) Fall back to name match
            if not existing:
                existing = (
                    self.db.query(InventoryItem)
                    .filter(func.lower(InventoryItem.name) == li.name.lower())
                    .first()
                )

            if existing:
                existing.quantity  += qty
                existing.updated_at = datetime.utcnow()
                li.matched_item_id  = existing.id
                results.append(existing)
                n_updated += 1
            else:
                item = InventoryItem(
                    name       = li.name,
                    sku        = li.parsed_sku,
                    quantity   = qty,
                    unit_price = li.unit_price,
                )
                self.db.add(item)
                self.db.flush()   # get the new id without committing
                li.matched_item_id = item.id
                results.append(item)
                n_created += 1

        self.db.commit()
        for item in results:
            self.db.refresh(item)

        logger.info(
            "Receipt %s: created %d, incremented %d item(s)",
            receipt_id, n_created, n_updated,
        )
        return results

    # ── Reports ───────────────────────────────────────────────────────────────

    def get_summary(self) -> dict:
        total_items  = self.db.query(func.count(InventoryItem.id)).scalar()
        total_value  = self.db.query(
            func.sum(InventoryItem.quantity * InventoryItem.unit_price)
        ).scalar() or 0
        low_stock    = self.db.query(InventoryItem).filter(
            InventoryItem.quantity <= InventoryItem.low_stock_threshold
        ).count()
        categories   = self.db.query(Category).count()

        return {
            "total_items":        total_items,
            "total_value":        float(total_value),
            "low_stock_count":    low_stock,
            "category_count":     categories,
        }
