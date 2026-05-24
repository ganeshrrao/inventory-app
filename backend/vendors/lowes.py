"""
vendors/lowes.py - Lowe's Product Catalog Adapter

Uses SerpApi's Lowe's engine (consistent with the Home Depot adapter).
Set LOWES_API_KEY to your SerpApi key to enable.

SerpApi Lowe's docs: https://serpapi.com/lowes-search-api
"""
import asyncio
import logging
from typing import Optional
from datetime import datetime

import httpx

from .base import VendorAdapter, ProductInfo

logger = logging.getLogger(__name__)

_SEARCH_URL  = "https://serpapi.com/search"
_PRODUCT_URL = "https://serpapi.com/search"


class RateLimiter:
    def __init__(self, calls_per_second: float = 2.0):
        self._min_interval = 1.0 / calls_per_second
        self._last_call: Optional[datetime] = None

    async def acquire(self):
        if self._last_call:
            elapsed = (datetime.utcnow() - self._last_call).total_seconds()
            wait = self._min_interval - elapsed
            if wait > 0:
                await asyncio.sleep(wait)
        self._last_call = datetime.utcnow()


class LowesAdapter(VendorAdapter):
    """
    Lowe's product catalog adapter via SerpApi.

    Env vars expected:
        LOWES_API_KEY   - your SerpApi key
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._rate   = RateLimiter(calls_per_second=2)
        self._client = httpx.AsyncClient(timeout=30.0)

    def _parse_product(self, data: dict) -> ProductInfo:
        """Normalize a SerpApi Lowe's product result → ProductInfo."""
        raw_price = data.get("price", "")
        price: Optional[float] = None
        if raw_price:
            try:
                price = float(str(raw_price).replace("$", "").replace(",", "").strip())
            except ValueError:
                pass

        return ProductInfo(
            sku        = str(data.get("item_number") or data.get("model_number") or ""),
            name       = data.get("title") or data.get("name") or "Unknown",
            brand      = data.get("brand"),
            description= data.get("description"),
            price      = price,
            image_url  = data.get("thumbnail") or data.get("image"),
            category   = data.get("category"),
            raw        = data,
        )

    async def lookup_sku(self, sku: str) -> Optional[ProductInfo]:
        """
        Look up a Lowe's item by item number or model number.
        Searches by the SKU string and returns the first exact match.
        """
        await self._rate.acquire()
        params = {
            "engine":  "lowes",
            "q":       sku,
            "api_key": self.api_key,
        }
        try:
            resp = await self._client.get(_SEARCH_URL, params=params)
            resp.raise_for_status()
            payload  = resp.json()
            results  = payload.get("organic_results") or payload.get("products") or []
            if not results:
                logger.info("SKU %s not found on Lowe's", sku)
                return None

            # Prefer an exact item_number or model_number match; fall back to first result
            sku_lower = sku.lower()
            for r in results:
                if (
                    str(r.get("item_number", "")).lower() == sku_lower
                    or str(r.get("model_number", "")).lower() == sku_lower
                ):
                    return self._parse_product(r)

            return self._parse_product(results[0])

        except httpx.HTTPStatusError as e:
            logger.error("Lowe's API error for SKU %s: %s", sku, e)
            raise
        except Exception as e:
            logger.error("Unexpected error looking up SKU %s on Lowe's: %s", sku, e)
            raise

    async def search_products(self, query: str, limit: int = 10) -> list[ProductInfo]:
        """Search Lowe's catalog by keyword."""
        await self._rate.acquire()
        params = {
            "engine":  "lowes",
            "q":       query,
            "api_key": self.api_key,
        }
        try:
            resp = await self._client.get(_SEARCH_URL, params=params)
            resp.raise_for_status()
            payload = resp.json()
            results = payload.get("organic_results") or payload.get("products") or []
            return [self._parse_product(r) for r in results[:limit]]
        except Exception as e:
            logger.error("Lowe's search failed for '%s': %s", query, e)
            return []

    async def get_price(self, sku: str, store_id: Optional[str] = None) -> Optional[float]:  # noqa: ARG002
        """Fetch current price for a SKU."""
        product = await self.lookup_sku(sku)
        if product:
            return product.price
        return None

    async def close(self):
        await self._client.aclose()
