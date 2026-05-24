"""
vendors/base.py - Abstract vendor adapter interface
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ProductInfo:
    sku: str
    name: str
    brand: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    image_url: Optional[str] = None
    category: Optional[str] = None
    unit: Optional[str] = None
    raw: dict = field(default_factory=dict)   # full vendor response


class VendorAdapter(ABC):
    """
    All vendor integrations implement this interface.
    Swap out adapters without changing business logic.
    """

    @abstractmethod
    async def lookup_sku(self, sku: str) -> Optional[ProductInfo]:
        """Fetch product details by SKU / item number."""
        ...

    @abstractmethod
    async def search_products(self, query: str, limit: int = 10) -> list[ProductInfo]:
        """Free-text product search."""
        ...

    @abstractmethod
    async def get_price(self, sku: str, store_id: Optional[str] = None) -> Optional[float]:
        """Get current price, optionally for a specific store."""
        ...
