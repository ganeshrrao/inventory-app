"""
vendors/home_depot.py - Home Depot Product Catalog Adapter

Uses SerpApi's Home Depot engines:
  - engine=home_depot_product  for single product lookup by item number
  - engine=home_depot           for keyword search

SerpApi docs: https://serpapi.com/home-depot-product-api
Set HOME_DEPOT_API_KEY to your SerpApi key.
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


class HomeDepotAdapter(VendorAdapter):
    """
    Home Depot product catalog adapter via SerpApi.

    Env vars expected:
        HOME_DEPOT_API_KEY   - your SerpApi key
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._rate   = RateLimiter(calls_per_second=2)
        self._client = httpx.AsyncClient(timeout=30.0)

    def _parse_product(self, data: dict) -> ProductInfo:
        """Normalize a SerpApi Home Depot product result → ProductInfo."""
        raw_price = data.get("price", "")
        price: Optional[float] = None
        if raw_price:
            try:
                price = float(str(raw_price).replace("$", "").replace(",", "").strip())
            except ValueError:
                pass

        images = data.get("images") or []
        image_url = images[0] if images else data.get("thumbnail")

        return ProductInfo(
            sku         = str(data.get("product_id") or data.get("model_number") or ""),
            name        = data.get("title") or data.get("name") or "Unknown",
            brand       = data.get("brand"),
            description = data.get("description"),
            price       = price,
            image_url   = image_url,
            category    = data.get("category"),
            raw         = data,
        )

    async def lookup_sku(self, sku: str) -> Optional[ProductInfo]:
        """Look up a single product by Home Depot item number (product_id)."""
        await self._rate.acquire()
        params = {
            "engine":     "home_depot_product",
            "product_id": sku,
            "api_key":    self.api_key,
        }
        try:
            resp = await self._client.get(_SERPAPI_URL, params=params)
            resp.raise_for_status()
            payload = resp.json()
            product_data = payload.get("product_results")
            if not product_data:
                logger.info("SKU %s not found on Home Depot", sku)
                return None
            return self._parse_product(product_data)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.info("SKU %s not found on Home Depot", sku)
                return None
            logger.error("HD API error for SKU %s: %s", sku, e)
            raise
        except Exception as e:
            logger.error("Unexpected error looking up SKU %s: %s", sku, e)
            raise

    async def search_products(self, query: str, limit: int = 10) -> list[ProductInfo]:
        """Search Home Depot catalog by keyword."""
        await self._rate.acquire()
        params = {
            "engine":  "home_depot",
            "q":       query,
            "api_key": self.api_key,
        }
        try:
            resp = await self._client.get(_SERPAPI_URL, params=params)
            resp.raise_for_status()
            payload  = resp.json()
            products = payload.get("organic_results") or []
            return [self._parse_product(p) for p in products[:limit]]
        except Exception as e:
            logger.error("HD search failed for '%s': %s", query, e)
            return []

    async def get_price(self, sku: str, store_id: Optional[str] = None) -> Optional[float]:  # noqa: ARG002
        product = await self.lookup_sku(sku)
        return product.price if product else None

    async def close(self):
        await self._client.aclose()
