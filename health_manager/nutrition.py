import json
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

    def item(self, fid, grams, name=None, low=None, high=None, confidence="手动确认"):
        food = self.foods.get(str(fid))
        grams = number(grams, 0.1, 10000, "克数")
        return validate_item({"name": name or (self.display(food) if food else "未匹配食物"),
                              "food_id": str(fid) if food else "", "grams": grams,
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
