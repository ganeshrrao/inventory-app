"""
utils/ocr_service.py - Receipt OCR + line-item extraction

Uses OpenAI Vision (gpt-4o) by default. Swap provider to Tesseract,
Google Cloud Vision, or AWS Textract by changing OCRProvider.
"""
import base64
import logging
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class OCRProvider(str, Enum):
    OPENAI     = "openai"
    GEMINI     = "gemini"
    GROQ       = "groq"
    GOOGLE     = "google_vision"
    TESSERACT  = "tesseract"


@dataclass
class ParsedLineItem:
    raw_text:   str
    name:       Optional[str]
    sku:        Optional[str]
    quantity:   int
    unit_price: Optional[float]


@dataclass
class ParsedReceipt:
    vendor_name:   Optional[str]
    purchase_date: Optional[str]
    total_amount:  Optional[float]
    raw_text:      str
    line_items:    list[ParsedLineItem]


class OCRService:
    """Extract and parse line items from receipt images."""

    RECEIPT_PROMPT = """
    You are a receipt parser. Analyze this receipt image and extract:
    1. Vendor/store name
    2. Purchase date (ISO format if possible)
    3. Total amount
    4. Each line item with: item name, SKU/item number if visible, quantity, unit price

    Respond in JSON only:
    {
      "vendor_name": "...",
      "purchase_date": "YYYY-MM-DD or null",
      "total_amount": 0.00,
      "line_items": [
        {
          "name": "...",
          "sku": "... or null",
          "quantity": 1,
          "unit_price": 0.00,
          "raw_text": "..."
        }
      ]
    }
    """

    def __init__(
        self,
        provider: OCRProvider = OCRProvider.OPENAI,
        api_key: Optional[str] = None,
        confidence_threshold: float = 0.7,
    ):
        self.provider             = provider
        self.api_key              = api_key
        self.confidence_threshold = confidence_threshold

    def _image_to_base64(self, image_path: str) -> str:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    async def extract_text(self, image_path: str) -> str:
        """Extract raw text from receipt image."""
        if self.provider == OCRProvider.OPENAI:
            return await self._openai_extract(image_path)
        elif self.provider == OCRProvider.TESSERACT:
            return self._tesseract_extract(image_path)
        raise NotImplementedError(f"Provider {self.provider} not yet implemented")

    async def parse_receipt(self, image_path: str) -> ParsedReceipt:
        """Full pipeline: image → structured receipt data."""
        if self.provider == OCRProvider.OPENAI:
            return await self._openai_parse(image_path)
        if self.provider == OCRProvider.GEMINI:
            return await self._gemini_parse(image_path)
        if self.provider == OCRProvider.GROQ:
            return await self._groq_parse(image_path)
        raw_text = await self.extract_text(image_path)
        return self._heuristic_parse(raw_text)

    # ── OpenAI Vision ────────────────────────────────────────────────────────
    async def _openai_extract(self, image_path: str) -> str:
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise RuntimeError("openai package not installed: pip install openai")

        client  = AsyncOpenAI(api_key=self.api_key)
        img_b64 = self._image_to_base64(image_path)
        ext     = Path(image_path).suffix.lstrip(".").lower()
        mime    = f"image/{ext if ext in ('png','jpg','jpeg','webp') else 'jpeg'}"

        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract all text from this receipt image."},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}"}},
                ],
            }],
            max_tokens=1000,
        )
        return response.choices[0].message.content or ""

    async def _openai_parse(self, image_path: str) -> ParsedReceipt:
        try:
            import json
            from openai import AsyncOpenAI
        except ImportError:
            raise RuntimeError("openai package not installed")

        client  = AsyncOpenAI(api_key=self.api_key)
        img_b64 = self._image_to_base64(image_path)
        ext     = Path(image_path).suffix.lstrip(".").lower()
        mime    = f"image/{ext if ext in ('png','jpg','jpeg','webp') else 'jpeg'}"

        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": self.RECEIPT_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}"}},
                ],
            }],
            max_tokens=2000,
            response_format={"type": "json_object"},
        )

        raw    = response.choices[0].message.content or "{}"
        data   = json.loads(raw)
        items  = [
            ParsedLineItem(
                raw_text   = li.get("raw_text", ""),
                name       = li.get("name"),
                sku        = li.get("sku"),
                quantity   = int(li.get("quantity", 1)),
                unit_price = float(li["unit_price"]) if li.get("unit_price") else None,
            )
            for li in data.get("line_items", [])
        ]
        return ParsedReceipt(
            vendor_name   = data.get("vendor_name"),
            purchase_date = data.get("purchase_date"),
            total_amount  = float(data["total_amount"]) if data.get("total_amount") else None,
            raw_text      = raw,
            line_items    = items,
        )

    def _image_to_base64_resized(self, image_path: str, max_px: int = 1568) -> tuple[str, str]:
        """Return (base64, mime) with longest dimension capped at max_px."""
        from PIL import Image as PILImage
        import io
        img = PILImage.open(image_path).convert("RGB")
        w, h = img.size
        if max(w, h) > max_px:
            scale = max_px / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), PILImage.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode(), "image/jpeg"

    # ── Groq Vision ──────────────────────────────────────────────────────────
    async def _groq_parse(self, image_path: str) -> ParsedReceipt:
        try:
            import json
            from groq import AsyncGroq
        except ImportError:
            raise RuntimeError("Install: pip install groq")

        img_b64, mime = self._image_to_base64_resized(image_path)

        client = AsyncGroq(api_key=self.api_key)
        response = await client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": self.RECEIPT_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}"}},
                ],
            }],
            response_format={"type": "json_object"},
            max_tokens=2000,
        )

        raw  = response.choices[0].message.content or "{}"
        raw  = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
        data = json.loads(raw)

        items = [
            ParsedLineItem(
                raw_text   = li.get("raw_text", ""),
                name       = li.get("name"),
                sku        = li.get("sku"),
                quantity   = int(li.get("quantity", 1)),
                unit_price = float(li["unit_price"]) if li.get("unit_price") else None,
            )
            for li in data.get("line_items", [])
        ]
        return ParsedReceipt(
            vendor_name   = data.get("vendor_name"),
            purchase_date = data.get("purchase_date"),
            total_amount  = float(data["total_amount"]) if data.get("total_amount") else None,
            raw_text      = raw,
            line_items    = items,
        )

    # ── Gemini Vision ────────────────────────────────────────────────────────
    async def _gemini_parse(self, image_path: str) -> ParsedReceipt:
        try:
            import json
            from google import genai
            from google.genai import types
            from PIL import Image
        except ImportError:
            raise RuntimeError("Install: pip install google-genai pillow")

        client = genai.Client(api_key=self.api_key)
        img    = Image.open(image_path)

        response = await client.aio.models.generate_content(
            model="gemini-1.5-flash",
            contents=[self.RECEIPT_PROMPT, img],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )

        raw  = response.text or "{}"
        # Strip markdown code fences if the model wraps the JSON
        raw  = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
        data = json.loads(raw)

        items = [
            ParsedLineItem(
                raw_text   = li.get("raw_text", ""),
                name       = li.get("name"),
                sku        = li.get("sku"),
                quantity   = int(li.get("quantity", 1)),
                unit_price = float(li["unit_price"]) if li.get("unit_price") else None,
            )
            for li in data.get("line_items", [])
        ]
        return ParsedReceipt(
            vendor_name   = data.get("vendor_name"),
            purchase_date = data.get("purchase_date"),
            total_amount  = float(data["total_amount"]) if data.get("total_amount") else None,
            raw_text      = raw,
            line_items    = items,
        )

    # ── Tesseract (local fallback) ────────────────────────────────────────────
    def _tesseract_extract(self, image_path: str) -> str:
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            raise RuntimeError("Install: pip install pytesseract pillow")
        img = Image.open(image_path)
        return pytesseract.image_to_string(img)

    # ── Heuristic parser (fallback when no LLM) ──────────────────────────────
    def _heuristic_parse(self, raw_text: str) -> ParsedReceipt:
        """Regex-based receipt parser — best-effort, less accurate than LLM."""
        lines   = raw_text.splitlines()
        items   = []
        total   = None
        date    = None
        vendor  = lines[0].strip() if lines else None

        price_re = re.compile(r"\$?\s*([\d,]+\.\d{2})")
        date_re  = re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b")
        sku_re   = re.compile(r"\b(\d{6,12})\b")

        for line in lines:
            dm = date_re.search(line)
            if dm and not date:
                date = dm.group(1)

            if re.search(r"\btotal\b", line, re.I):
                pm = price_re.search(line)
                if pm:
                    total = float(pm.group(1).replace(",", ""))
                continue

            pm = price_re.search(line)
            if pm:
                price = float(pm.group(1).replace(",", ""))
                sm    = sku_re.search(line)
                name  = re.sub(r"[\$\d.,]", "", line).strip() or None
                items.append(ParsedLineItem(
                    raw_text=line, name=name,
                    sku=sm.group(1) if sm else None,
                    quantity=1, unit_price=price,
                ))

        return ParsedReceipt(
            vendor_name=vendor, purchase_date=date,
            total_amount=total, raw_text=raw_text, line_items=items,
        )
