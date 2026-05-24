"""
vendors/amazon.py - Amazon Product Catalog Adapter

Uses SerpApi's Amazon engines:
  - engine=amazon_product  for single product lookup by ASIN
  - engine=amazon           for keyword search

SerpApi docs: https://serpapi.com/amazon-product-api
Set AMAZON_API_KEY to your SerpApi key to enable.
"""
import asyncio
import logging
from typing import Optional
from datetime import datetime

import httpx

from .base import VendorAdapter, ProductInfo

logger = logging.getLogger(__name__)

_SERPAPI_URL = "https://serpapi.com/search"


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


class AmazonAdapter(VendorAdapter):
    """
    Amazon product catalog adapter via SerpApi.

    Env vars expected:
        AMAZON_API_KEY   - your SerpApi key
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._rate   = RateLimiter(calls_per_second=2)
        self._client = httpx.AsyncClient(timeout=30.0)

    def _parse_price(self, data: dict) -> Optional[float]:
        """Extract a float price from various shapes Amazon/SerpApi returns."""
        # Product detail: price is a string like "$29.99"
        raw = data.get("price")
        if isinstance(raw, str):
            try:
                return float(raw.replace("$", "").replace(",", "").strip())
            except ValueError:
                pass
        # Search results: price is {"value": 29.99, "symbol": "$"}
        if isinstance(raw, dict):
            try:
                return float(raw.get("value") or 0) or None
            except (ValueError, TypeError):
                pass
        return None

    def _parse_product(self, data: dict) -> ProductInfo:
        """Normalize a SerpApi Amazon product result → ProductInfo."""
        # Images: product detail has list of dicts, search has a thumbnail string
        images = data.get("images") or []
        if images and isinstance(images[0], dict):
            image_url = images[0].get("src") or images[0].get("link")
        else:
            image_url = data.get("thumbnail")

        # Category: product detail has a list, search results may not
        categories = data.get("categories") or []
        category = categories[0].get("name") if categories else None

        return ProductInfo(
            sku         = data.get("asin") or "",
            name        = data.get("title") or "Unknown",
            brand       = data.get("brand"),
            description = _first_bullet(data),
            price       = self._parse_price(data),
            image_url   = image_url,
            category    = category,
            raw         = data,
        )

    async def lookup_sku(self, sku: str) -> Optional[ProductInfo]:
        """
        Look up an Amazon product by ASIN (e.g. B08N5WRWNW).
        Falls back to a keyword search if the ASIN lookup returns nothing,
        so model numbers and UPC codes can also surface results.
        """
        await self._rate.acquire()

        # Try direct ASIN lookup first
        if _looks_like_asin(sku):
            params = {
                "engine":  "amazon_product",
                "asin":    sku,
                "api_key": self.api_key,
            }
            try:
                resp = await self._client.get(_SERPAPI_URL, params=params)
                resp.raise_for_status()
                payload      = resp.json()
                product_data = payload.get("product_results")
                if product_data:
                    return self._parse_product(product_data)
            except httpx.HTTPStatusError as e:
                if e.response.status_code != 404:
                    logger.error("Amazon ASIN lookup error for %s: %s", sku, e)
                    raise
            except Exception as e:
                logger.error("Unexpected error in Amazon ASIN lookup for %s: %s", sku, e)
                raise

        # Fallback: search by SKU string (covers model numbers, UPCs, etc.)
        results = await self.search_products(sku, limit=1)
        if results:
            return results[0]

        logger.info("SKU %s not found on Amazon", sku)
        return None

    async def search_products(self, query: str, limit: int = 10) -> list[ProductInfo]:
        """Search Amazon catalog by keyword."""
        await self._rate.acquire()
        params = {
            "engine":  "amazon",
            "q":       query,
            "api_key": self.api_key,
        }
        try:
            resp = await self._client.get(_SERPAPI_URL, params=params)
            resp.raise_for_status()
            payload = resp.json()
            results = payload.get("organic_results") or []
            return [self._parse_product(r) for r in results[:limit]]
        except Exception as e:
            logger.error("Amazon search failed for '%s': %s", query, e)
            return []

    async def get_price(self, sku: str, store_id: Optional[str] = None) -> Optional[float]:  # noqa: ARG002
        product = await self.lookup_sku(sku)
        return product.price if product else None

    async def close(self):
        await self._client.aclose()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _looks_like_asin(s: str) -> bool:
    """ASINs are exactly 10 alphanumeric characters, usually starting with B."""
    return len(s) == 10 and s.isalnum()


def _first_bullet(data: dict) -> Optional[str]:
    """Use the first feature bullet as description when no description field exists."""
    desc = data.get("description")
    if desc:
        return desc
    bullets = data.get("feature_bullets") or []
    return bullets[0] if bullets else None
