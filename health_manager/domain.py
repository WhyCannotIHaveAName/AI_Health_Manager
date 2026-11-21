import math
from datetime import date

KINDS = {"weight": (1, 650, "kg"), "sleep": (0, 24, "小时"),
         "exercise": (0, 1440, "分钟"), "water": (0, 15000, "ml")}
LABELS = {"weight": "体重", "sleep": "睡眠", "exercise": "活动", "water": "饮水", "meal": "饮食"}
NUTRIENTS = ("kcal", "protein", "fat", "carbs", "fiber", "sodium")


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
        if not isinstance(nutrients, dict):
            raise ValueError("营养数据格式错误")
        nutrients = {n: None if nutrients.get(n) is None else number(
            nutrients[n], 0, 100000 if n == "sodium" else 1000, n) for n in NUTRIENTS}
    return {"name": str(item["name"])[:200], "grams": grams,
            "grams_low": low, "grams_high": high, "per100": nutrients,
            "source": str(item.get("source", "待补充"))[:500],
            "food_id": str(item.get("food_id", ""))[:40],
            "confidence": str(item.get("confidence", "待确认"))[:60]}


def totals(items):
    result = {}
    for n in NUTRIENTS:
        known = [i for i in items if i.get("per100") and i["per100"].get(n) is not None]
        result[n] = {"value": sum(i["per100"][n] * i["grams"] / 100 for i in known),
                     "low": sum(i["per100"][n] * i["grams_low"] / 100 for i in known),
                     "high": sum(i["per100"][n] * i["grams_high"] / 100 for i in known),
                     "missing": len(items) - len(known)}
    return result
