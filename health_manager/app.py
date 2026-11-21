import copy
import json
import os
import queue
import sys
import threading
import tkinter as tk
from datetime import date, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox
import customtkinter as ctk
from . import __version__
from . import ai
from .domain import KINDS, LABELS, NUTRIENTS, number, totals
from .nutrition import Catalog
from .secrets import load_key, save_key
from .store import Store

BG = "#F3F5F1"
INK = "#173D38"
MUTED = "#6A7F78"
TEAL = "#287D6B"
WHITE = "#FFFFFF"
FONT = "Microsoft YaHei UI"


def resource_dir():
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1])) / "data"


def user_dir():
    exe = Path(sys.executable).parent
    if (exe / "portable.flag").exists():
        return exe / "userdata"
    return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "AIHealthManager"


class App(ctk.CTk):
    def __init__(self, data_dir=None):
        super().__init__()
        self.title("栖衡 · AI Health Manager")
        width = min(1180, max(900, self.winfo_screenwidth() - 80))
        height = min(820, max(600, self.winfo_screenheight() - 120))
        self.geometry(f"{width}x{height}+20+20")
        self.minsize(900, 600)
        self.configure(fg_color=BG)
        self.data_dir = Path(data_dir) if data_dir else user_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.store = Store(self.data_dir / "health.db")
        self.catalog = Catalog(resource_dir())
        self.key_error = ""
        try:
            self.key = load_key(self.data_dir / "api.secret")
        except (OSError, ValueError):
            self.key = ""
            self.key_error = "已保存的密钥无法解密，请重新填写。"
        self.page = "overview"
        self.busy = False
        self.events = queue.Queue()
        self.draft = []
        self.meal_id = None
        self.meal_day = date.today().isoformat()
        self.meal_slot = "午餐"
        self.meal_text = ""
        self.meal_image = None
        self.meal_notes = ""
        self.latest_advice = None
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        sidebar = ctk.CTkFrame(self, width=208, corner_radius=0, fg_color=INK)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        self.label(sidebar, "栖 衡", 32, "#E6F2CE", True).pack(anchor="w", padx=28, pady=(35, 0))
        self.label(sidebar, "AI HEALTH MANAGER", 11, "#A6C5BB").pack(anchor="w", padx=29, pady=(6, 35))
        self.nav = {}
        for name, title in [("overview", "今日概览"), ("log", "身体记录"), ("meal", "饮食记录"), ("insight", "健康回顾"), ("history", "全部记录"), ("settings", "设置与备份")]:
            b = ctk.CTkButton(sidebar, text=title, anchor="w", width=172, height=44, corner_radius=10,
                             font=(FONT, 14), fg_color="transparent", hover_color="#29554C",
                             command=lambda n=name: self.show(n))
            b.pack(padx=18, pady=4)
            self.nav[name] = b
        self.label(sidebar, "每天留下一点记录。\n慢慢找到自己的节奏。", 12, "#B5CEC5").pack(side="bottom", padx=24, pady=30, anchor="w")
        self.shell = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.shell.grid(row=0, column=1, sticky="nsew", padx=30, pady=(24, 12))
        self.shell.grid_columnconfigure(0, weight=1)
        self.shell.grid_rowconfigure(1, weight=1)
        self.status = self.label(self.shell, "本机保存 · AI 功能需自行填写 DeepSeek API Key", 11, MUTED)
        self.status.grid(row=2, column=0, sticky="w", pady=(10, 0))
        self.header = ctk.CTkFrame(self.shell, fg_color="transparent")
        self.header.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        self.body = None
        self.show("overview")
        self.after(120, self.poll)
        self.protocol("WM_DELETE_WINDOW", self.close)

    def label(self, parent, text, size=14, color=INK, bold=False, **kw):
        return ctk.CTkLabel(parent, text=text, font=(FONT, size, "bold" if bold else "normal"),
                            text_color=color, justify="left", anchor="w", **kw)

    def button(self, parent, text, command, secondary=False, **kw):
        return ctk.CTkButton(parent, text=text, command=command, font=(FONT, 13), height=38,
                            fg_color="#E3EBE4" if secondary else TEAL,
                            text_color=INK if secondary else WHITE, hover_color="#BCD6C8" if secondary else "#206453", **kw)

    def card(self, parent):
        return ctk.CTkFrame(parent, fg_color=WHITE, corner_radius=14, border_width=1, border_color="#E3E9E1")

    def entry(self, parent, placeholder="", value="", width=180):
        e = ctk.CTkEntry(parent, placeholder_text=placeholder, height=38, width=width,
                         font=(FONT, 13), fg_color=WHITE, border_color="#D8E1D8", text_color=INK)
        if value != "":
            e.insert(0, str(value))
        return e

    def show(self, page, capture=True):
        if capture and self.page == "meal" and self.body and self.body.winfo_exists():
            self.capture_meal()
        self.page = page
        for name, button in self.nav.items():
            button.configure(fg_color="#346451" if name == page else "transparent")
        for w in self.header.winfo_children():
            w.destroy()
        titles = {"overview": ("让健康，有迹可循", "从今天的一次记录开始。"), "log": ("身体记录", "体重、睡眠、活动与饮水，按自己的节奏记录。"),
                  "meal": ("记下这一餐", "文字或照片输入，识别后核对食物和份量。"), "insight": ("最近 14 天的健康回顾", "从已有记录中寻找变化和可完成的小步骤。"),
                  "history": ("全部记录", "查看、修改和删除已经保存的记录。"), "settings": ("设置与备份", "连接你的 DeepSeek 账户，管理本机数据。")}
        title, subtitle = titles[page]
        self.label(self.header, date.today().strftime("%Y / %m / %d") + "     ·     栖衡", 12, MUTED).pack(anchor="w")
        self.label(self.header, title, 27, bold=True).pack(anchor="w", pady=(10, 4))
        self.label(self.header, subtitle, 13, MUTED).pack(anchor="w")
        if self.body:
            self.body.destroy()
        self.body = ctk.CTkScrollableFrame(self.shell, fg_color=BG, corner_radius=0)
        self.body.grid(row=1, column=0, sticky="nsew")
        self.body.grid_columnconfigure(0, weight=1)
        getattr(self, "render_" + page)()

    def error(self, error):
        from .diagnostics import write_error
        write_error(self.data_dir / "last-error.json", error)
        # Never display raw network responses or keys.
        if isinstance(error, (ai.AIError, ValueError)):
            message = str(error)
        elif isinstance(error, OSError):
            message = "文件或系统操作失败，请检查路径、磁盘空间和写入权限。"
        else:
            message = "操作未完成，请重试。已有记录保存在本机。"
        messagebox.showerror("操作未完成", message, parent=self)

    def report_callback_exception(self, exc, value, traceback):
        self.error(value)

    def run_job(self, work, done):
        if self.busy:
            messagebox.showinfo("正在处理", "请等待当前 AI 请求完成。", parent=self)
            return
        self.busy = True
        self.status.configure(text="正在连接 DeepSeek…（最长约 75 秒，可继续浏览记录）")
        def run():
            try:
                self.events.put((done, work(), None))
            except Exception as e:
                self.events.put((done, None, e))
        threading.Thread(target=run, daemon=True).start()

    def poll(self):
        try:
            done, value, error = self.events.get_nowait()
            self.busy = False
            self.status.configure(text="本机保存 · AI 请求已结束")
            if error:
                self.error(error)
            else:
                done(value)
        except queue.Empty:
            pass
        self.after(120, self.poll)

    def close(self):
        self.store.close()
        self.destroy()

    def render_overview(self):
        today = self.store.records(date.today().isoformat())
        recent = self.store.recent(30)
        cards = ctk.CTkFrame(self.body, fg_color="transparent")
        cards.pack(fill="x", pady=(0, 16))
        cards.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="c")
        for col, kind in enumerate(KINDS):
            rows = [r for r in today if r["kind"] == kind]
            if kind == "weight":
                value = f"{rows[0]['value']:g}" if rows else "—"
            else:
                value = f"{sum(r['value'] for r in rows):g}" if rows else "—"
            c = self.card(cards)
            c.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 6, 0))
            self.label(c, "今日" + LABELS[kind], 12, MUTED).pack(anchor="w", padx=18, pady=(15, 4))
            self.label(c, value, 28, TEAL, True).pack(anchor="w", padx=18)
            self.label(c, KINDS[kind][2], 12, MUTED).pack(anchor="w", padx=18, pady=(0, 14))
        band = ctk.CTkFrame(self.body, fg_color="#DFEACF", corner_radius=14)
        band.pack(fill="x", pady=(0, 16))
        self.label(band, "今天，先照顾好一件小事", 18, bold=True).pack(anchor="w", padx=22, pady=(18, 4))
        self.label(band, "记下一顿饭，或昨晚的睡眠。记录是了解自己的线索。", 13).pack(anchor="w", padx=22, pady=(0, 14))
        self.button(band, "+ 身体记录", lambda: self.show("log"), width=120).pack(side="left", padx=(22, 10), pady=(0, 18))
        self.button(band, "+ 饮食记录", lambda: self.show("meal"), secondary=True, width=120).pack(side="left", pady=(0, 18))
        chart = self.card(self.body)
        chart.pack(fill="x", pady=(0, 16))
        self.label(chart, "体重趋势 · 最近 30 天", 16, bold=True).pack(anchor="w", padx=20, pady=(16, 0))
        self.label(chart, "每日最后一次记录；空白日期没有记录。", 12, MUTED).pack(anchor="w", padx=20)
        canvas = tk.Canvas(chart, height=170, bg=WHITE, highlightthickness=0)
        canvas.pack(fill="x", padx=18, pady=(4, 14))
        byday = {}
        for r in recent:
            if r["kind"] == "weight" and r["day"] not in byday:
                byday[r["day"]] = r["value"]
        points = sorted(byday.items())
        canvas.bind("<Configure>", lambda event: self.draw_chart(canvas, points))
        self.label(self.body, "最近记录", 16, bold=True).pack(anchor="w", pady=(0, 10))
        for row in recent[:4]:
            self.record_tile(row, self.body, actions=False)
        if not recent:
            self.empty("还没有记录。点击上方按钮，保存你的第一条。")

    def draw_chart(self, canvas, points):
        canvas.delete("all")
        w = canvas.winfo_width()
        if not points:
            canvas.create_text(w / 2, 80, text="记录体重后，这里会呈现变化", fill=MUTED, font=(FONT, 13))
            return
        values = [v for _, v in points]
        low, high = min(values) - .5, max(values) + .5
        start = date.today() - timedelta(days=29)
        for i in range(3):
            y = 20 + 52 * i
            canvas.create_line(50, y, w - 20, y, fill="#E7ECE7")
            canvas.create_text(25, y, text=f"{high - (high-low)*i/2:.1f}", fill=MUTED, font=(FONT, 10))
        xy = []
        for day, value in points:
            x = 55 + (date.fromisoformat(day) - start).days / 29 * max(1, w - 85)
            y = 20 + (high - value) / (high - low) * 104
            xy.extend((x, y))
        if len(xy) > 2:
            canvas.create_line(*xy, fill=TEAL, width=3)
        for x, y in zip(xy[::2], xy[1::2]):
            canvas.create_oval(x-4, y-4, x+4, y+4, fill=TEAL, outline=WHITE, width=2)
        canvas.create_text(54, 150, text=start.strftime("%m/%d"), anchor="w", fill=MUTED, font=(FONT, 10))
        canvas.create_text(w-20, 150, text="今天", anchor="e", fill=MUTED, font=(FONT, 10))

    def empty(self, text):
        self.label(self.body, text, 14, MUTED, wraplength=680).pack(anchor="w", padx=8, pady=25)

    def render_log(self, record=None):
        for child in self.body.winfo_children():
            child.destroy()
        record = record or {}
        card = self.card(self.body)
        card.pack(fill="x")
        self.label(card, "修改记录" if record else "新增记录", 18, bold=True).pack(anchor="w", padx=24, pady=(22, 12))
        self.label(card, "日期（睡眠按醒来当天记录）", 13, MUTED).pack(anchor="w", padx=24)
        day = self.entry(card, value=record.get("day", date.today().isoformat()))
        day.pack(anchor="w", padx=24, pady=(5, 15))
        self.label(card, "记录类型", 13, MUTED).pack(anchor="w", padx=24)
        kind = ctk.CTkOptionMenu(card, values=[LABELS[k] for k in KINDS], font=(FONT, 13), fg_color=TEAL, button_color=TEAL, width=180)
        kind.set(LABELS.get(record.get("kind", "weight")))
        kind.pack(anchor="w", padx=24, pady=(5, 12))
        units = self.label(card, "", 13, MUTED)
        units.pack(anchor="w", padx=24)
        def unit_changed(value):
            key = next(k for k in KINDS if LABELS[k] == value)
            units.configure(text="数值 · " + KINDS[key][2] + ("（小时可填 7.5）" if key == "sleep" else ""))
        kind.configure(command=unit_changed)
        unit_changed(kind.get())
        value = self.entry(card, "请输入数值", record.get("value", ""))
        value.pack(anchor="w", padx=24, pady=(5, 15))
        self.label(card, "备注（可选）", 13, MUTED).pack(anchor="w", padx=24)
        note = ctk.CTkTextbox(card, height=100, font=(FONT, 13), fg_color=BG, text_color=INK)
        note.insert("1.0", record.get("note", ""))
        note.pack(fill="x", padx=24, pady=(5, 18))
        def save():
            try:
                key = next(k for k in KINDS if LABELS[k] == kind.get())
                self.store.save({"day": day.get(), "kind": key, "value": value.get(), "note": note.get("1.0", "end-1c")}, record.get("id"))
                self.latest_advice = None
                self.status.configure(text="记录已保存在本机")
                self.show("overview")
            except Exception as e:
                self.error(e)
        self.button(card, "保存记录", save, width=150).pack(anchor="w", padx=24, pady=(0, 24))

    def capture_meal(self):
        if hasattr(self, "meal_input") and self.meal_input.winfo_exists():
            self.meal_text = self.meal_input.get("1.0", "end-1c")
            self.meal_day = self.meal_date.get()
            self.meal_slot = self.meal_slot_widget.get()

    def render_meal(self):
        form = self.card(self.body)
        form.pack(fill="x", pady=(0, 14))
        top = ctk.CTkFrame(form, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=18)
        self.meal_date = self.entry(top, value=self.meal_day, width=155)
        self.meal_date.pack(side="left", padx=(0, 12))
        self.meal_slot_widget = ctk.CTkOptionMenu(top, values=["早餐", "午餐", "晚餐", "加餐", "其他"], fg_color=TEAL, button_color=TEAL, font=(FONT, 13), width=120)
        self.meal_slot_widget.set(self.meal_slot)
        self.meal_slot_widget.pack(side="left")
        self.label(form, "吃了什么？也可以补充照片中的份量和剩余量。", 14).pack(anchor="w", padx=20)
        self.meal_input = ctk.CTkTextbox(form, height=100, font=(FONT, 14), fg_color=BG, text_color=INK)
        self.meal_input.insert("1.0", self.meal_text)
        self.meal_input.pack(fill="x", padx=20, pady=(8, 12))
        self.label(form, Path(self.meal_image).name if self.meal_image else "尚未选择照片 · 支持 JPG / PNG / WebP", 12, MUTED, wraplength=650).pack(anchor="w", padx=20)
        bar = ctk.CTkFrame(form, fg_color="transparent")
        bar.pack(fill="x", padx=20, pady=12)
        self.button(bar, "选择照片", self.pick_image, True, width=110).pack(side="left", padx=(0, 8))
        if self.meal_image:
            self.button(bar, "移除照片", self.remove_image, True, width=100).pack(side="left", padx=(0, 8))
        self.button(bar, "发送给 DeepSeek 识别", self.identify, width=200).pack(side="left")
        self.label(form, "点击识别将发送本餐文字和所选照片，按你的 API 账户计费。照片不保存到记录中。", 11, MUTED, wraplength=700).pack(anchor="w", padx=20, pady=(0, 18))
        self.label(self.body, "核对食物与份量", 18, bold=True).pack(anchor="w", pady=(6, 4))
        self.label(self.body, "营养值来自数据库或你填写的包装标签；份量范围仅反映重量估计。", 12, MUTED).pack(anchor="w", pady=(0, 10))
        if self.meal_notes:
            self.label(self.body, self.meal_notes, 13, MUTED, wraplength=700).pack(anchor="w", pady=(0, 10))
        for idx, item in enumerate(self.draft):
            tile = self.card(self.body)
            tile.pack(fill="x", pady=(0, 8))
            text = f"{item['name']}  ·  {item['grams']:g} g  [{item['grams_low']:g}–{item['grams_high']:g} g]"
            self.label(tile, text, 14, bold=True, wraplength=600).pack(anchor="w", padx=16, pady=(12, 3))
            self.label(tile, item["source"] + "  |  " + item["confidence"], 11, MUTED, wraplength=620).pack(anchor="w", padx=16)
            if item.get("per100") and item["per100"].get("kcal") is not None:
                self.label(tile, f"约 {item['per100']['kcal'] * item['grams'] / 100:.0f} kcal", 12, TEAL).pack(anchor="w", padx=16, pady=3)
            tools = ctk.CTkFrame(tile, fg_color="transparent")
            tools.pack(anchor="w", padx=16, pady=(6, 12))
            self.button(tools, "修改 / 匹配", lambda i=idx: self.item_dialog(i), True, width=110).pack(side="left", padx=(0, 8))
            self.button(tools, "移除", lambda i=idx: self.remove_item(i), True, width=70).pack(side="left")
        if self.draft:
            self.label(self.body, self.nutrition_text(self.draft), 13, TEAL, wraplength=710).pack(anchor="w", pady=12)
        buttons = ctk.CTkFrame(self.body, fg_color="transparent")
        buttons.pack(fill="x", pady=12)
        self.button(buttons, "+ 手动添加食物", self.item_dialog, True, width=160).pack(side="left", padx=(0, 10))
        self.button(buttons, "确认并保存这一餐", self.save_meal, width=180).pack(side="left", padx=(0, 10))
        self.button(buttons, "新的一餐", self.new_meal, True, width=100).pack(side="left")

    def nutrition_text(self, items):
        t = totals(items)
        kcal = t["kcal"]
        if kcal["missing"] == len(items):
            text = "热量待补充（尚无可计算的数据）"
        else:
            text = f"已匹配部分约 {kcal['value']:.0f} kcal（份量估计 {kcal['low']:.0f}–{kcal['high']:.0f}）"
        if 0 < kcal["missing"] < len(items):
            text += f"；{kcal['missing']} 项热量待补充"
        for key, label in [("protein", "蛋白质"), ("fat", "脂肪"), ("carbs", "碳水"), ("fiber", "纤维"), ("sodium", "钠")]:
            if t[key]["missing"] == len(items):
                text += f"  ·  {label} 待补充"
                continue
            text += f"  ·  {label} {t[key]['value']:.1f}{'mg' if key == 'sodium' else 'g'}"
            if t[key]["missing"]:
                text += "（部分缺失）"
        return text

    def pick_image(self):
        if self.busy:
            messagebox.showinfo("正在识别", "请等待识别结束后更换照片。", parent=self)
            return
        path = filedialog.askopenfilename(parent=self, title="选择食物照片", filetypes=[("食物照片", "*.jpg *.jpeg *.png *.webp")])
        if path:
            self.capture_meal()
            self.meal_image = path
            self.show("meal")

    def remove_image(self):
        if self.busy:
            return
        self.meal_image = None
        self.show("meal")

    def identify(self):
        self.capture_meal()
        if not self.key:
            messagebox.showinfo("先填写 API Key", "请到“设置与备份”填写你的 DeepSeek API Key。", parent=self)
            return
        if not self.meal_text.strip() and not self.meal_image:
            messagebox.showinfo("补充这一餐", "请输入食物描述或选择照片。", parent=self)
            return
        if self.draft and not messagebox.askyesno("重新识别", "重新识别将替换当前尚未保存的食物列表，继续？", parent=self):
            return
        key, text, image = self.key, self.meal_text, self.meal_image
        def done(result):
            self.capture_meal()
            if self.meal_text != text or self.meal_image != image:
                self.status.configure(text="识别期间输入已变化，本次结果未应用，请重新识别")
                return
            self.draft, self.meal_notes = result
            if self.page == "meal":
                self.show("meal")
            else:
                self.status.configure(text="饮食识别已完成，请到饮食记录核对并保存")
        self.run_job(lambda: ai.analyze_meal(key, text, image, self.catalog), done)

    def remove_item(self, idx):
        if self.busy:
            return
        self.draft.pop(idx)
        self.show("meal")

    def new_meal(self):
        if self.busy:
            messagebox.showinfo("正在识别", "等待识别结束后再新建一餐。", parent=self)
            return
        if self.draft and not messagebox.askyesno("新的一餐", "放弃当前草稿并新建一餐？", parent=self):
            return
        self.capture_meal()
        self.draft, self.meal_id, self.meal_image = [], None, None
        self.meal_text, self.meal_notes, self.meal_day = "", "", date.today().isoformat()
        self.show("meal", capture=False)

    def save_meal(self):
        self.capture_meal()
        if self.busy:
            messagebox.showinfo("正在识别", "请在识别完成后核对并保存。", parent=self)
            return
        try:
            self.store.save({"kind": "meal", "day": self.meal_day, "slot": self.meal_slot,
                             "note": self.meal_text, "items": self.draft}, self.meal_id)
            self.latest_advice = None
            self.meal_id, self.draft, self.meal_image = None, [], None
            self.meal_text, self.meal_notes = "", ""
            # Leaving the meal page must not recapture stale fields.
            self.meal_input.delete("1.0", "end")
            self.status.configure(text="这一餐已保存在本机")
            self.show("history")
        except Exception as e:
            self.error(e)

    def item_dialog(self, idx=None):
        if self.busy:
            messagebox.showinfo("正在识别", "请等待识别结束后修改食物。", parent=self)
            return
        self.capture_meal()
        item = copy.deepcopy(self.draft[idx]) if idx is not None else {}
        win = ctk.CTkToplevel(self)
        win.title("核对食物 · 数据库与包装标签")
        win.geometry("800x730")
        win.minsize(720, 620)
        win.transient(self)
        win.after(100, win.grab_set)
        body = ctk.CTkScrollableFrame(win, fg_color=BG)
        body.pack(fill="both", expand=True, padx=12, pady=12)
        self.label(body, "选择相同食物与生熟状态", 19, bold=True).pack(anchor="w", pady=(8, 10))
        searchrow = ctk.CTkFrame(body, fg_color="transparent")
        searchrow.pack(fill="x")
        query = self.entry(searchrow, "中文常见食物 / 英文关键词", width=460)
        query.pack(side="left", padx=(0, 10))
        matches = tk.Listbox(body, height=6, font=(FONT, 11), bg=WHITE, fg=INK, exportselection=False, activestyle="none")
        selected = {"id": item.get("food_id", ""), "source": item.get("source", "用户标签 / 手动录入")}
        found = []
        def search():
            found[:] = self.catalog.search(query.get(), 100)
            matches.delete(0, "end")
            for f in found:
                matches.insert("end", f["id"] + " · " + self.catalog.display(f))
        self.button(searchrow, "搜索", search, True, width=90).pack(side="left")
        query.bind("<Return>", lambda e: search())
        matches.pack(fill="x", pady=(8, 6))
        self.label(body, "中文索引覆盖常见食材，其余可用英文查找。选择后自动填入每100g营养。", 11, MUTED).pack(anchor="w")
        name = self.entry(body, "食物名称", item.get("name", ""), width=650)
        name.pack(anchor="w", pady=12)
        gramsrow = ctk.CTkFrame(body, fg_color="transparent")
        gramsrow.pack(fill="x")
        entries = {}
        for key, label in [("grams", "份量 g"), ("grams_low", "估计下界 g"), ("grams_high", "估计上界 g")]:
            col = ctk.CTkFrame(gramsrow, fg_color="transparent")
            col.pack(side="left", padx=(0, 14))
            self.label(col, label, 12, MUTED).pack(anchor="w")
            entries[key] = self.entry(col, value=item.get(key, "100"), width=150)
            entries[key].pack(pady=5)
        source_label = self.label(body, selected["source"], 11, MUTED, wraplength=680)
        source_label.pack(anchor="w", pady=8)
        self.label(body, "每 100 g 营养值（空白表示未知；包装标签可覆盖）", 13, bold=True).pack(anchor="w", pady=(5, 8))
        grid = ctk.CTkFrame(body, fg_color="transparent")
        grid.pack(fill="x")
        nutrition = {}
        original = {"per100": item.get("per100")}
        labels = {"kcal": "热量 kcal", "protein": "蛋白质 g", "fat": "脂肪 g", "carbs": "碳水 g", "fiber": "纤维 g", "sodium": "钠 mg"}
        for col, n in enumerate(NUTRIENTS):
            row, column = divmod(col, 3)
            frame = ctk.CTkFrame(grid, fg_color="transparent")
            frame.grid(row=row, column=column, sticky="w", padx=(0, 20), pady=4)
            self.label(frame, labels[n], 12, MUTED).pack(anchor="w")
            val = (item.get("per100") or {}).get(n)
            nutrition[n] = self.entry(frame, value="" if val is None else val, width=180)
            nutrition[n].pack(pady=3)
        def choose(event=None):
            if not matches.curselection():
                return
            food = found[matches.curselection()[0]]
            selected["id"], selected["source"] = food["id"], "USDA SR Legacy · FDC " + food["id"]
            original["per100"] = food["per100"]
            name.delete(0, "end")
            name.insert(0, self.catalog.display(food))
            source_label.configure(text=selected["source"])
            for n, e in nutrition.items():
                e.delete(0, "end")
                if food["per100"].get(n) is not None:
                    e.insert(0, str(food["per100"][n]))
        matches.bind("<<ListboxSelect>>", choose)
        def save():
            try:
                per100 = {n: None if not e.get().strip() else number(e.get(), 0, 100000 if n == "sodium" else 1000, labels[n]) for n, e in nutrition.items()}
                source = selected["source"]
                fid = selected["id"]
                if per100 != original["per100"]:
                    source, fid = "用户标签 / 手动录入", ""
                from .domain import validate_item
                clean = validate_item({"name": name.get(), **{k: v.get() for k, v in entries.items()},
                                       "per100": per100, "source": source, "food_id": fid, "confidence": "用户已核对"})
                if idx is None:
                    self.draft.append(clean)
                else:
                    self.draft[idx] = clean
                win.destroy()
                self.show("meal")
            except Exception as e:
                self.error(e)
        self.button(body, "应用到这一餐", save, width=180).pack(anchor="w", pady=16)
        search()

    def snapshot(self):
        rows = self.store.recent(14)
        coverage = {LABELS[k]: len({r["day"] for r in rows if r["kind"] == k}) for k in LABELS}
        sanitized = []
        for r in rows[:300]:
            row = {k: v for k, v in r.items() if k != "id"}
            if row["kind"] == "meal":
                row["nutrition"] = totals(row["items"])
                row["items"] = [{k: i[k] for k in ("name", "grams", "grams_low", "grams_high", "source")} for i in row["items"]]
            sanitized.append(row)
        return {"period_start": (date.today()-timedelta(days=13)).isoformat(), "period_end": date.today().isoformat(),
                "coverage_days": coverage, "total_records": len(rows), "included_records": len(sanitized),
                "note": "仅用户已记录的部分；睡眠/活动/饮水可一天多条，体重按每日最新记录看趋势。不能假定饮食覆盖全天。超过300条时仅包含最新300条。", "records": sanitized}

    def render_insight(self):
        snap = self.snapshot()
        card = self.card(self.body)
        card.pack(fill="x", pady=(0, 16))
        self.label(card, "已有的线索", 18, bold=True).pack(anchor="w", padx=22, pady=(20, 8))
        text = "  ·  ".join(f"{k} {v}/14 天" for k, v in snap["coverage_days"].items())
        self.label(card, text, 13, MUTED, wraplength=690).pack(anchor="w", padx=22, pady=(0, 12))
        self.label(card, "将发送最近14天的记录、备注和营养估计，不包含照片、API Key或更早的记录。", 12, MUTED, wraplength=700).pack(anchor="w", padx=22, pady=(0, 12))
        self.button(card, "预览将发送的摘要", self.preview_snapshot, True, width=200).pack(anchor="w", padx=22, pady=(0, 10))
        self.button(card, "发送摘要并生成建议", self.generate_advice, width=200).pack(anchor="w", padx=22, pady=(0, 22))
        if self.latest_advice:
            result = self.latest_advice
            advicecard = self.card(self.body)
            advicecard.pack(fill="x")
            self.label(advicecard, "AI 的观察", 18, bold=True).pack(anchor="w", padx=22, pady=(20, 8))
            self.label(advicecard, result["summary"], 14, wraplength=700).pack(anchor="w", padx=22, pady=(0, 15))
            for suggestion in result["suggestions"]:
                self.label(advicecard, "• " + suggestion, 14, wraplength=700).pack(anchor="w", padx=22, pady=(0, 12))
            self.label(advicecard, result["encouragement"], 14, TEAL, wraplength=700).pack(anchor="w", padx=22, pady=(5, 20))
        else:
            self.empty("建议会显示在这里。也可以只记录，暂不调用 AI。")
        self.label(self.body, "AI 帮助回顾生活习惯，不用于诊断或调整用药。", 11, MUTED).pack(anchor="w", pady=18)

    def preview_snapshot(self):
        win = ctk.CTkToplevel(self)
        win.title("将发送给 DeepSeek 的数据")
        win.geometry("760x620")
        win.transient(self)
        text = ctk.CTkTextbox(win, font=(FONT, 12), wrap="word")
        text.pack(fill="both", expand=True, padx=16, pady=16)
        text.insert("1.0", json.dumps(self.snapshot(), ensure_ascii=False, indent=2))
        text.configure(state="disabled")

    def generate_advice(self):
        if not self.key:
            messagebox.showinfo("先填写 API Key", "请到设置中填写自己的 DeepSeek API Key。", parent=self)
            return
        snapshot = self.snapshot()
        if not snapshot["records"]:
            messagebox.showinfo("先记录一些线索", "至少保存一条记录后再生成建议。", parent=self)
            return
        def done(result):
            if self.snapshot() != snapshot:
                self.status.configure(text="记录已变化，请基于更新后的摘要重新生成建议")
                return
            self.latest_advice = result
            if self.page == "insight":
                self.show("insight")
            else:
                self.status.configure(text="AI 建议已生成，可到健康回顾查看")
        key = self.key
        self.run_job(lambda: ai.advice(key, snapshot), done)

    def record_tile(self, row, parent, actions=True):
        tile = self.card(parent)
        tile.pack(fill="x", pady=(0, 9))
        title = f"{row['day']}   ·   {LABELS[row['kind']]}"
        if row["kind"] == "meal":
            title += " · " + row.get("slot", "") + "   " + "、".join(i["name"] for i in row["items"])
            detail = self.nutrition_text(row["items"])
        else:
            title += f"   {row['value']:g} {KINDS[row['kind']][2]}"
            detail = row.get("note", "")
        self.label(tile, title, 13, bold=True, wraplength=680).pack(anchor="w", padx=16, pady=(12, 5))
        if detail:
            self.label(tile, detail[:500], 12, MUTED, wraplength=680).pack(anchor="w", padx=16, pady=(0, 8))
        if actions:
            tools = ctk.CTkFrame(tile, fg_color="transparent")
            tools.pack(anchor="w", padx=16, pady=(0, 12))
            self.button(tools, "修改", lambda: self.edit_record(row), True, width=80).pack(side="left", padx=(0, 8))
            self.button(tools, "删除", lambda: self.delete_record(row), True, width=80).pack(side="left")

    def render_history(self):
        bar = ctk.CTkFrame(self.body, fg_color="transparent")
        bar.pack(fill="x", pady=(0, 14))
        kind = ctk.CTkOptionMenu(bar, values=["全部类型", *LABELS.values()], fg_color=TEAL, button_color=TEAL, font=(FONT, 13))
        kind.pack(side="left", padx=(0, 12))
        query = self.entry(bar, "日期 / 食物 / 备注", width=300)
        query.pack(side="left", padx=(0, 12))
        listing = ctk.CTkFrame(self.body, fg_color="transparent")
        listing.pack(fill="both", expand=True)
        def refresh(*args):
            for w in listing.winfo_children():
                w.destroy()
            rows = [r for r in self.store.records() if (kind.get() == "全部类型" or LABELS[r["kind"]] == kind.get()) and query.get().lower() in json.dumps(r, ensure_ascii=False).lower()]
            self.label(listing, f"共 {len(rows)} 条" + (" · 显示最近 200 条，请搜索缩小范围" if len(rows) > 200 else ""), 12, MUTED).pack(anchor="w", pady=(0, 12))
            for row in rows[:200]:
                self.record_tile(row, listing)
        kind.configure(command=refresh)
        query.bind("<Return>", refresh)
        self.button(bar, "筛选", refresh, True, width=90).pack(side="left")
        refresh()

    def edit_record(self, row):
        if self.busy:
            messagebox.showinfo("AI 正在处理", "请等待当前请求结束后编辑。", parent=self)
            return
        if row["kind"] == "meal":
            if self.draft and not messagebox.askyesno("打开记录", "放弃尚未保存的饮食草稿并打开这条记录？", parent=self):
                return
            self.draft, self.meal_id = copy.deepcopy(row["items"]), row["id"]
            self.meal_day, self.meal_slot, self.meal_text = row["day"], row.get("slot", "其他"), row["note"]
            self.meal_image, self.meal_notes = None, ""
            self.show("meal")
        else:
            self.show("log")
            self.render_log(row)

    def delete_record(self, row):
        if messagebox.askyesno("删除记录", f"删除 {row['day']} 的这条{LABELS[row['kind']]}记录？此操作无法撤销。", parent=self):
            self.store.delete(row["id"])
            self.latest_advice = None
            self.show("history")

    def render_settings(self):
        card = self.card(self.body)
        card.pack(fill="x", pady=(0, 16))
        self.label(card, "连接 DeepSeek", 18, bold=True).pack(anchor="w", padx=22, pady=(20, 8))
        self.label(card, "仅连接 api.deepseek.com · 模型 deepseek-flash（支持图片）", 12, MUTED).pack(anchor="w", padx=22)
        keyentry = self.entry(card, "DeepSeek API Key", self.key, width=530)
        keyentry.configure(show="•")
        keyentry.pack(anchor="w", padx=22, pady=12)
        remember = ctk.CTkCheckBox(card, text="在这台电脑记住密钥（Windows 用户加密）", font=(FONT, 13), text_color=INK, fg_color=TEAL)
        if (self.data_dir / "api.secret").exists():
            remember.select()
        remember.pack(anchor="w", padx=22, pady=(0, 12))
        self.label(card, "不勾选时仅在本次运行中使用。密钥不写入备份；健康记录以本机 SQLite 保存。", 12, MUTED, wraplength=690).pack(anchor="w", padx=22)
        if self.key_error:
            self.label(card, self.key_error, 12, "#A65A36").pack(anchor="w", padx=22)
        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.pack(anchor="w", padx=22, pady=18)
        def save():
            try:
                key = keyentry.get().strip()
                if key and (len(key) < 8 or len(key) > 500 or any(c.isspace() for c in key)):
                    raise ValueError("请填写有效的 API Key")
                save_key(self.data_dir / "api.secret", key if remember.get() else "")
                self.key, self.key_error = key, ""
                self.status.configure(text="密钥已更新" if key else "密钥已清除")
            except Exception as e:
                self.error(e)
        def test():
            key = keyentry.get().strip()
            self.run_job(lambda: ai.request_json(key, '只返回 json {"ok":true}', "连接测试，不含健康数据"),
                         lambda _: messagebox.showinfo("连接成功", "DeepSeek 已正常返回。请点击保存密钥以应用设置。", parent=self))
        self.button(buttons, "保存密钥", save, width=130).pack(side="left", padx=(0, 10))
        self.button(buttons, "测试连接（少量计费）", test, True, width=200).pack(side="left")
        data = self.card(self.body)
        data.pack(fill="x", pady=(0, 16))
        self.label(data, "数据与备份", 18, bold=True).pack(anchor="w", padx=22, pady=(20, 8))
        self.label(data, str(self.data_dir), 11, MUTED, wraplength=690).pack(anchor="w", padx=22)
        self.label(data, "导出文件包含健康记录，请自行妥善保管。导入会合并新记录，已有同 ID 记录不覆盖。", 12, MUTED, wraplength=690).pack(anchor="w", padx=22, pady=8)
        bar = ctk.CTkFrame(data, fg_color="transparent")
        bar.pack(anchor="w", padx=22, pady=(8, 20))
        self.button(bar, "导出 JSON 备份", self.export_backup, True, width=170).pack(side="left", padx=(0, 10))
        self.button(bar, "导入 JSON 备份", self.import_backup, True, width=170).pack(side="left")
        self.label(self.body, f"栖衡 v{__version__}  ·  {len(self.catalog.foods):,} 项 USDA SR Legacy 食物\n数据来源：FoodData Central · April 2018 · CC0\n中文食物为人工检索别名；混合菜与地区配方需要用户核对。", 12, MUTED, wraplength=690).pack(anchor="w", pady=8)

    def export_backup(self):
        path = filedialog.asksaveasfilename(parent=self, title="导出健康记录", defaultextension=".json", initialfile=f"health-backup-{date.today()}.json", filetypes=[("JSON 备份", "*.json")])
        if path:
            try:
                Path(path).write_text(json.dumps(self.store.export_data(), ensure_ascii=False, indent=2), encoding="utf-8")
                self.status.configure(text="备份已导出，不含 API Key")
            except Exception as e:
                self.error(e)

    def import_backup(self):
        path = filedialog.askopenfilename(parent=self, filetypes=[("JSON 备份", "*.json")])
        if path:
            try:
                if Path(path).stat().st_size > 50 * 1024 * 1024:
                    raise ValueError("备份文件请小于 50 MB")
                data = json.loads(Path(path).read_text(encoding="utf-8"))
                count = self.store.import_data(data)
                self.latest_advice = None
                self.status.configure(text=f"已导入 {count} 条新记录")
            except Exception as e:
                self.error(e)


def main():
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("green")
    App().mainloop()
