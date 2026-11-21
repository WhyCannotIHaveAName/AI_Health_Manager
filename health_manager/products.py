"""Read-only public packaged-food labels. No account key or meal notes are sent."""
import json
import threading
import time
import unicodedata
import urllib.parse
import urllib.request
from .domain import nutrients_per100

ROOT = "https://world.openfoodfacts.org"
USER_AGENT = "AIHealthManager/0.2 (https://github.com/WhyCannotIHaveAName/AI_Health_Manager)"
FIELDS = "code,product_name,product_name_zh,brands,quantity,product_quantity_unit,nutriments"


def valid_barcode(value):
    code = str(value or "").strip()
    if len(code) not in (8, 12, 13, 14) or not code.isascii() or not code.isdigit():
        return False
    digits = [int(c) for c in code]
    checksum = sum(n * (3 if i % 2 == 0 else 1) for i, n in enumerate(reversed(digits[:-1])))
    return (checksum + digits[-1]) % 10 == 0


def product_data(product):
    if not isinstance(product, dict) or not valid_barcode(product.get("code")):
        return None
    raw = product.get("nutriments")
    if not isinstance(raw, dict):
        return None
    def val(name):
        value = raw.get(name + "_100g")
        if value is None or isinstance(value, bool):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    kcal = val("energy-kcal")
    if kcal is None:
        kj = val("energy-kj")
        if kj is None:
            kj = val("energy")
        kcal = kj / 4.184 if kj is not None else None
    sodium = val("sodium")
    salt = val("salt")
    sodium = sodium * 1000 if sodium is not None else (salt * 400 if salt is not None else None)
    try:
        nutrients = nutrients_per100({"kcal": kcal, "protein": val("proteins"), "fat": val("fat"),
                                      "carbs": val("carbohydrates"), "fiber": val("fiber"), "sodium": sodium})
    except ValueError:
        return None
    if nutrients["kcal"] is None:
        return None
    code = str(product["code"])
    unit = "ml" if str(product.get("product_quantity_unit", "")).lower() == "ml" else "g"
    return {"code": code, "name": str(product.get("product_name_zh") or product.get("product_name") or "商品")[:200],
            "brands": str(product.get("brands", ""))[:200], "quantity": str(product.get("quantity", ""))[:100],
            "per100": nutrients, "unit": unit, "source_url": ROOT + "/product/" + code}


class Products:
    def __init__(self, opener=None):
        self.opener = opener or urllib.request.build_opener()
        self.cache = {}
        self.lock = threading.Lock()
        self.next_request = 0

    def _read(self, url, interval):
        if url in self.cache:
            return self.cache[url]
        # OFF allows 10 searches/min and 15 barcode reads/min per IP.
        with self.lock:
            delay = self.next_request - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            self.next_request = time.monotonic() + interval
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            with self.opener.open(request, timeout=8) as response:
                raw = response.read(1500001)
            if len(raw) > 1500000:
                raise ValueError("商品数据库响应过大")
            data = json.loads(raw)
            self.cache[url] = data
            return data

    def barcode(self, code):
        if not valid_barcode(code):
            return None
        # v2 remains supported for flat `nutriments`; v3.6 currently returned
        # an empty legacy nutriments object in the public API smoke check.
        data = self._read(ROOT + "/api/v2/product/" + str(code) + ".json?" + urllib.parse.urlencode({"fields": FIELDS}), 4.2)
        return product_data(data.get("product")) if isinstance(data, dict) else None

    def brand(self, brand):
        if not isinstance(brand, str) or not brand.strip():
            return []
        tag = unicodedata.normalize("NFKD", brand.lower().strip())
        tag = "-".join("".join(c for c in tag if not unicodedata.combining(c)).split())[:80]
        query = {"brands_tags": tag, "page_size": 12, "fields": FIELDS}
        data = self._read(ROOT + "/api/v2/search?" + urllib.parse.urlencode(query), 6.2)
        return [p for row in data.get("products", []) if (p := product_data(row))] if isinstance(data, dict) else []
