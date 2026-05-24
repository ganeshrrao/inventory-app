import base64
import logging
import os
import subprocess
import tempfile

import cv2
import httpx
import numpy as np

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "InventoryApp/1.0 (github.com/your-repo)"}

# Free Open Food Facts family — food, beauty, pet food, all same API shape
_OFF_BASES = [
    "https://world.openfoodfacts.org",
    "https://world.openbeautyfacts.org",
    "https://world.openpetfoodfacts.org",
]
_UPC_URL = "https://api.upcitemdb.com/prod/trial/lookup?upc={barcode}"

_THIS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_NODE_SCRIPT = os.path.join(_THIS_DIR, "barcode_helper", "decode.js")


def _call_node(image_bytes: bytes) -> str | None:
    """Write bytes to a temp file, call Node/ZXing, return decoded string or None."""
    if not os.path.exists(_NODE_SCRIPT):
        return None
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name
        result = subprocess.run(
            ["node", _NODE_SCRIPT, tmp_path],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            code = result.stdout.strip()
            if code:
                return code
    except Exception as e:
        logger.warning("Node.js barcode decode failed: %s", e)
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
    return None


def _encode_png(img) -> bytes:
    ok, buf = cv2.imencode(".png", img)
    return buf.tobytes() if ok else b""


def _variants(img):
    """Yield preprocessed BGR images, best-first for real camera photos."""
    yield img                                                       # 1 original

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 2 — CLAHE (local contrast boost, handles uneven lighting)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    clahe_gray = clahe.apply(gray)
    yield cv2.cvtColor(clahe_gray, cv2.COLOR_GRAY2BGR)

    # 3 — unsharp mask on CLAHE (recovers blurry edges)
    blurred = cv2.GaussianBlur(clahe_gray, (0, 0), 3)
    unsharp = cv2.addWeighted(clahe_gray, 1.8, blurred, -0.8, 0)
    yield cv2.cvtColor(unsharp, cv2.COLOR_GRAY2BGR)

    # 4 — heavy unsharp for very blurry images
    blurred2 = cv2.GaussianBlur(gray, (0, 0), 5)
    heavy = cv2.addWeighted(gray, 2.5, blurred2, -1.5, 0)
    yield cv2.cvtColor(heavy, cv2.COLOR_GRAY2BGR)

    # 5 — Otsu on unsharp (clean binary)
    _, otsu = cv2.threshold(unsharp, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    yield cv2.cvtColor(otsu, cv2.COLOR_GRAY2BGR)

    # 6 — adaptive threshold (best for uneven lighting / shadows)
    adapt = cv2.adaptiveThreshold(
        clahe_gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 8
    )
    yield cv2.cvtColor(adapt, cv2.COLOR_GRAY2BGR)

    # 7 — adaptive threshold on heavy-unsharp
    adapt2 = cv2.adaptiveThreshold(
        heavy, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 6
    )
    yield cv2.cvtColor(adapt2, cv2.COLOR_GRAY2BGR)


def decode_barcode_image(image_bytes: bytes) -> str | None:
    arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return None

    # Resize very large images (phone photos can be 4K+) — barcode only needs ~800px wide
    h, w = img.shape[:2]
    if w > 1200:
        scale = 1200 / w
        img = cv2.resize(img, (1200, int(h * scale)), interpolation=cv2.INTER_AREA)

    for variant in _variants(img):
        code = _call_node(_encode_png(variant))
        if code:
            return code

    return None


async def decode_barcode_via_vision(image_bytes: bytes, api_key: str) -> str | None:
    """Ask GPT-4o to read the barcode number directly from the image."""
    try:
        from openai import AsyncOpenAI
    except ImportError:
        return None
    try:
        mime = "image/jpeg"
        if image_bytes[:4] == b"\x89PNG":
            mime = "image/png"
        elif image_bytes[:4] == b"RIFF":
            mime = "image/webp"
        img_b64 = base64.b64encode(image_bytes).decode()
        client = AsyncOpenAI(api_key=api_key)
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Look at this image. Find the barcode or UPC/EAN number "
                            "(either from the bars themselves or from the digits printed "
                            "below or beside the bars). "
                            "Reply with ONLY the digits, no spaces, no other text. "
                            "If no barcode is present reply with the single word NONE."
                        ),
                    },
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}"}},
                ],
            }],
            max_tokens=30,
        )
        raw = (response.choices[0].message.content or "").strip()
        digits = "".join(c for c in raw if c.isdigit())
        if digits:
            return digits
    except Exception as e:
        logger.warning("GPT-4o vision barcode failed: %s", e)
    return None


async def lookup_barcode_via_ai(barcode: str, api_key: str) -> dict | None:
    """Ask GPT-4o to identify a product by its barcode number (text-only, no image)."""
    try:
        import json as _json
        from openai import AsyncOpenAI
    except ImportError:
        return None
    try:
        client = AsyncOpenAI(api_key=api_key)
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": (
                    f"What consumer product has the UPC/EAN barcode number {barcode}? "
                    "Reply in JSON only with these fields: "
                    '{"name": "...", "brand": "...", "description": "..."}. '
                    "Use null for any field you are not confident about. "
                    'If you have no idea what the product is, reply with {"name": null}.'
                ),
            }],
            max_tokens=120,
            response_format={"type": "json_object"},
        )
        data = _json.loads(response.choices[0].message.content or "{}")
        if data.get("name"):
            return {
                "barcode": barcode,
                "name": data["name"],
                "brand": data.get("brand") or None,
                "description": data.get("description") or None,
                "image_url": None,
                "source": "ai",
            }
    except Exception as e:
        logger.warning("GPT-4o product lookup failed for %s: %s", barcode, e)
    return None


async def lookup_barcode(barcode: str, openai_api_key: str = "") -> dict | None:
    async with httpx.AsyncClient(timeout=8.0) as client:
        # 1. Open Food Facts family (food, beauty, pet food) — free, no key
        for base in _OFF_BASES:
            try:
                r = await client.get(f"{base}/api/v2/product/{barcode}.json", headers=_HEADERS)
                if r.status_code == 200:
                    data = r.json()
                    if data.get("status") == 1:
                        p = data["product"]
                        name = p.get("product_name_en") or p.get("product_name") or ""
                        if name:
                            brand = (p.get("brands") or "").split(",")[0].strip() or None
                            desc = (
                                p.get("generic_name")
                                or (p.get("categories") or "").split(",")[0].strip()
                                or None
                            )
                            source = base.split("//")[1].split(".")[1]  # e.g. "openfoodfacts"
                            return {
                                "barcode": barcode,
                                "name": name,
                                "brand": brand,
                                "description": desc,
                                "image_url": p.get("image_url"),
                                "source": source,
                            }
            except Exception as e:
                logger.warning("%s lookup failed for %s: %s", base, barcode, e)

        # 2. UPC Item DB — free trial, 100 req/day, covers general retail
        try:
            r = await client.get(_UPC_URL.format(barcode=barcode), headers=_HEADERS)
            if r.status_code == 200:
                items = r.json().get("items") or []
                if items:
                    item = items[0]
                    return {
                        "barcode": barcode,
                        "name": item.get("title") or "",
                        "brand": item.get("brand") or None,
                        "description": item.get("description") or None,
                        "image_url": (item.get("images") or [None])[0],
                        "source": "upc_item_db",
                    }
        except Exception as e:
            logger.warning("UPC Item DB lookup failed for %s: %s", barcode, e)

    # 3. GPT-4o text lookup — identifies Costco, Kirkland, hardware, and other
    #    items not in consumer food databases (requires OPENAI_API_KEY)
    if openai_api_key:
        result = await lookup_barcode_via_ai(barcode, openai_api_key)
        if result:
            return result

    return None
