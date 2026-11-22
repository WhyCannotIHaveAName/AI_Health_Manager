"""Rebuild the bundled CC0 nutrition catalog from the official USDA CSV ZIP."""
import csv
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

URL = "https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_sr_legacy_food_csv_2018-04.zip"
NUTRIENTS = {"1008": "kcal", "1003": "protein", "1004": "fat", "1005": "carbs", "1079": "fiber", "1093": "sodium"}


def build(archive, output):
    raw = Path(archive).read_bytes()
    z = zipfile.ZipFile(io.BytesIO(raw))
    def table(name):
        path = next(n for n in z.namelist() if n.endswith("/" + name + ".csv"))
        return csv.DictReader(io.StringIO(z.read(path).decode("utf-8-sig")))
    foods = {r["fdc_id"]: {"id": r["fdc_id"], "name": r["description"], "per100": {n: None for n in NUTRIENTS.values()}} for r in table("food")}
    for row in table("food_nutrient"):
        if row["nutrient_id"] in NUTRIENTS and row["fdc_id"] in foods and row["amount"]:
            foods[row["fdc_id"]]["per100"][NUTRIENTS[row["nutrient_id"]]] = float(row["amount"])
    catalog = {"source": "USDA FoodData Central SR Legacy (April 2018)", "url": URL,
               "archive_sha256": hashlib.sha256(raw).hexdigest(), "license": "CC0-1.0",
               "foods": list(foods.values())}
    Path(output).write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Built {len(foods)} foods; SHA256 {catalog['archive_sha256']}")


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
