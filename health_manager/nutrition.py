import json
import re
from pathlib import Path
from .domain import validate_item, number


class Catalog:
    def __init__(self, folder):
        self.meta = json.loads((Path(folder) / "foods.json").read_text(encoding="utf-8"))
        self.foods = {f["id"]: f for f in self.meta["foods"]}
        self.aliases = json.loads((Path(folder) / "aliases.json").read_text(encoding="utf-8"))

    def display(self, food):
        aliases = [a for a, fid in self.aliases.items() if fid == food["id"]]
        return (aliases[0] + " · " if aliases else "") + food["name"]

    def search(self, query, limit=60):
        query = query.strip().lower()
        if not query:
            ids = list(dict.fromkeys(self.aliases.values()))
            return [self.foods[i] for i in ids][:limit]
        matched = [fid for a, fid in self.aliases.items() if query in a.lower()]
        words = query.split()
        matched.extend(f["id"] for f in self.foods.values() if all(w in f["name"].lower() for w in words))
        return [self.foods[i] for i in dict.fromkeys(matched)][:limit]

    def prompt_catalog(self):
        return [{"id": f["id"], "name": self.display(f)} for f in self.search("", 200)]

    def candidates(self, terms, limit=10):
        """Retrieve from all records; the AI is no longer limited to 50 aliases."""
        if not isinstance(terms, list):
            terms = []
        scores = {}
        stop = {"and", "with", "the", "of", "a", "food", "prepared"}
        for term in terms[:4]:
            if not isinstance(term, str):
                continue
            words = set(re.findall(r"[a-z]+", term.lower())) - stop
            for f in self.search(term, limit):
                scores[f["id"]] = scores.get(f["id"], 0) + 10
            if not words:
                continue
            for f in self.foods.values():
                name = f["name"].lower()
                overlap = sum(w in name for w in words)
                if overlap >= max(1, len(words)-1):
                    scores[f["id"]] = scores.get(f["id"], 0) + overlap / len(words)
        ids = sorted(scores, key=lambda fid: (-scores[fid], self.foods[fid]["name"]))[:limit]
        return [self.foods[fid] for fid in ids]

    def item(self, fid, grams, name=None, low=None, high=None, confidence="手动确认", unit="g"):
        food = self.foods.get(str(fid))
        grams = number(grams, 0.1, 10000, "克数")
        return validate_item({"name": name or (self.display(food) if food else "未匹配食物"),
                              "food_id": str(fid) if food else "", "grams": grams,
                              "unit": unit, "source_kind": "database" if food else "unknown",
                              "source_url": f"https://fdc.nal.usda.gov/food-details/{fid}/nutrients" if food else "",
                              "grams_low": low if low is not None else grams,
                              "grams_high": high if high is not None else grams,
                              "per100": food["per100"] if food else None,
                              "source": f"USDA SR Legacy · FDC {fid}" if food else "待补充 · 未匹配数据库",
                              "confidence": confidence})

    def parse_ai(self, data):
        if not isinstance(data, dict) or not isinstance(data.get("items"), list) or len(data["items"]) > 40:
            raise ValueError("AI 返回的食物列表格式不正确，请重试或手动添加")
        items = []
        for row in data["items"]:
            if not isinstance(row, dict) or not isinstance(row.get("name"), str) or not row["name"].strip():
                raise ValueError("AI 返回的食物名称无效")
            grams = number(row.get("grams"), 0.1, 10000, "AI 估计克数")
            # Unknown IDs NEVER become made-up nutrient values.
            items.append(self.item(row.get("food_id"), grams, row["name"],
                                   row.get("grams_low", grams * .75), row.get("grams_high", grams * 1.3),
                                   "AI 估计 · 请核对"))
        if not items:
            raise ValueError("未识别到食物，请补充描述或手动添加")
        return items, str(data.get("notes", ""))[:1500]
