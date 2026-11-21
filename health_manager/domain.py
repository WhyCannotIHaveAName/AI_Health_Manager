import math
from datetime import date

KINDS = {"weight": (1, 650, "kg"), "sleep": (0, 24, "小时"),
         "exercise": (0, 1440, "分钟"), "water": (0, 15000, "ml")}
LABELS = {"weight": "体重", "sleep": "睡眠", "exercise": "活动", "water": "饮水", "meal": "饮食"}
NUTRIENTS = ("kcal", "protein", "fat", "carbs", "fiber", "sodium")
SOURCE_KINDS = ("database", "product_label", "estimate", "reference_estimate", "user_label", "unknown")


def nutrient_limit(name):
    return 100000 if name == "sodium" else (1000 if name == "kcal" else 100)


def nutrients_per100(values):
    if not isinstance(values, dict):
        raise ValueError("营养数据格式错误")
    return {n: None if values.get(n) is None else number(values[n], 0, nutrient_limit(n), n) for n in NUTRIENTS}


def number(value, low, high, label="数值"):
    if isinstance(value, bool):
        raise ValueError(f"{label}请输入数字")
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label}请输入数字") from None
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{label}需在 {low}–{high} 之间")
    return value


def valid_day(value):
    try:
        parsed = date.fromisoformat(value)
    except (ValueError, TypeError):
        raise ValueError("日期请使用 YYYY-MM-DD") from None
    if parsed > date.today() or parsed.year < 1900:
        raise ValueError("日期应在 1900 年至今天之间")
    return parsed.isoformat()


def validate_record(record):
    if not isinstance(record, dict):
        raise ValueError("记录格式错误")
    kind = record.get("kind")
    if kind not in (*KINDS, "meal"):
        raise ValueError("未知记录类型")
    result = {"day": valid_day(record.get("day")), "kind": kind,
              "note": str(record.get("note", ""))[:4000]}
    if kind == "meal":
        items = record.get("items")
        if not isinstance(items, list) or not 1 <= len(items) <= 40:
            raise ValueError("每餐应包含 1–40 项食物")
        result["items"] = [validate_item(i) for i in items]
        result["slot"] = str(record.get("slot", "其他"))[:20]
    else:
        low, high, _ = KINDS[kind]
        result["value"] = number(record.get("value"), low, high, LABELS[kind])
    return result


def validate_item(item):
    if not isinstance(item, dict) or not str(item.get("name", "")).strip():
        raise ValueError("请填写食物名称")
    grams = number(item.get("grams"), 0.1, 10000, "食物克数")
    low = number(item.get("grams_low", grams), 0, grams, "份量下界")
    high = number(item.get("grams_high", grams), grams, 20000, "份量上界")
    nutrients = item.get("per100")
    if nutrients is not None:
        nutrients = nutrients_per100(nutrients)
    inferred = "database" if str(item.get("source", "")).startswith("USDA") else ("user_label" if nutrients else "unknown")
    source_kind = item.get("source_kind", inferred)
    if source_kind not in SOURCE_KINDS:
        raise ValueError("未知营养来源类型")
    unit = item.get("unit", "g")
    if unit not in ("g", "ml"):
        raise ValueError("份量单位应为 g 或 ml")
    estimated = item.get("estimated_nutrients", [])
    if not isinstance(estimated, list) or any(n not in NUTRIENTS for n in estimated):
        raise ValueError("估算字段格式错误")
    density_low = nutrients_per100(item["per100_low"]) if item.get("per100_low") is not None else nutrients
    density_high = nutrients_per100(item["per100_high"]) if item.get("per100_high") is not None else nutrients
    if nutrients:
        for n, value in nutrients.items():
            if value is not None and (not density_low or not density_high or density_low[n] is None or density_high[n] is None or not density_low[n] <= value <= density_high[n]):
                raise ValueError("营养估算范围应包含中心值")
    from urllib.parse import urlparse
    url = str(item.get("source_url", ""))[:1000]
    if url and (urlparse(url).scheme != "https" or urlparse(url).hostname not in ("fdc.nal.usda.gov", "world.openfoodfacts.org")):
        raise ValueError("营养来源链接不受支持")
    return {"name": str(item["name"])[:200], "grams": grams, "unit": unit,
            "grams_low": low, "grams_high": high, "per100": nutrients,
            "per100_low": density_low, "per100_high": density_high,
            "source_kind": source_kind, "source_url": url,
            "estimated_nutrients": list(dict.fromkeys(estimated)),
            "estimate_reason": str(item.get("estimate_reason", ""))[:1000],
            "source": str(item.get("source", "待补充"))[:500],
            "food_id": str(item.get("food_id", ""))[:40],
            "confidence": str(item.get("confidence", "待确认"))[:60]}


def totals(items):
    result = {}
    for n in NUTRIENTS:
        known = [i for i in items if i.get("per100") and i["per100"].get(n) is not None]
        result[n] = {"value": sum(i["per100"][n] * i["grams"] / 100 for i in known),
                     "low": sum((i.get("per100_low") or i["per100"])[n] * i["grams_low"] / 100 for i in known),
                     "high": sum((i.get("per100_high") or i["per100"])[n] * i["grams_high"] / 100 for i in known),
                     "missing": len(items) - len(known)}
    return result
