import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import csv
import smtplib
import os
import sys
import json
import random
import threading
import time
import re
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate, make_msgid
from email.header import Header
from dotenv import load_dotenv
import pystray
from PIL import Image, ImageDraw
from openai import OpenAI

# ── PyInstaller EXE / 通常スクリプト 両対応のベースディレクトリ ──
def _base_dir() -> str:
    """EXE実行時は _MEIPASS、スクリプト実行時はファイルの親ディレクトリを返す"""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS          # type: ignore[attr-defined]
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = _base_dir()

# ── 書き込みが必要なファイルは実行ファイルと同じフォルダに置く ──
def _runtime_dir() -> str:
    """EXE実行時は exe 本体と同じフォルダ、スクリプト時はソースフォルダを返す"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

RUNTIME_DIR = _runtime_dir()

# .env の読み込み（EXE内部の _MEIPASS から）
load_dotenv(os.path.join(BASE_DIR, ".env"))

CSV_FILE         = os.path.join(BASE_DIR,    "users.csv")
SENT_LOG_FILE    = os.path.join(RUNTIME_DIR, "sent_log.json")        # 送信済みメールを記録するファイル
TEMPLATE_FILE    = os.path.join(RUNTIME_DIR, "mail_templates.json")  # 件名・本文テンプレートを記録するファイル
DAILY_CFG_FILE   = os.path.join(RUNTIME_DIR, "daily_config.json")   # 毎日の送信進捗を記録するファイル

# 毎日必ず最初に送る固定宛先
FIXED_DAILY_USER = {"id": "fixed", "name": "sunny",
                    "email": "sunny365.25days@gmail.com",
                    "last_name": "", "first_name": ""}

# デフォルトテンプレート
DEFAULT_TEMPLATE = {
    "name": "基本テンプレート（Alexandra）",
    "subject": "リモートでのエンジニア協力のご相談",
    "body": (
        "{name}様\n\n"
        "お世話になっております。Alexandraと申します。\n\n"
        "突然のご連絡、失礼いたします。\n\n"
        "私は日本国籍を有しており、現在シンガポールに在住しております。"
        "来年、日本への移住を予定しております。\n\n"
        "移住に先立ち、日本の開発環境に慣れることを目的として、"
        "個人としてリモートで協力できる機会を探しております。\n\n"
        "これまでいくつかの企業様とお話しする中で、"
        "海外在住のまま参画することの難しさも理解しております。"
        "そのため、まずは短期間のトライアルのような形でご一緒させていただき、"
        "実務を通じて、私の経験やスキルがチームやプロジェクトに"
        "どのように価値をもたらせるかをご確認いただければと考えております。\n\n"
        "私はアメリカの大学を卒業後、10年以上にわたり"
        "シニアエンジニア・テックリード・PMとしての経験を積んでおります。"
        "立ち上がりは比較的スムーズに対応可能です。\n\n"
        "実務上のメリットをご実感いただければ、"
        "その後の関わり方や条件について、"
        "双方にとって納得感のある形でご相談させていただければ幸いです。\n\n"
        "もしご興味をお持ちいただけましたら、"
        "一度お話しさせていただけますと幸いです。\n\n"
        "お忙しいところ恐れ入りますが、何卒よろしくお願い申し上げます。\n\n"
        "Alexandra\n"
        "alexandrajohn419@gmail.com"
    ),
}

# ══════════════════════════════════════════
#  テンプレート管理（件名・本文の保存・読み込み）
# ══════════════════════════════════════════
def load_templates() -> list[dict]:
    """保存済みテンプレート一覧を返す [{name, subject, body}, ...]"""
    if not os.path.exists(TEMPLATE_FILE):
        # 初回：デフォルトテンプレートを自動登録
        save_templates([DEFAULT_TEMPLATE])
        return [DEFAULT_TEMPLATE]
    with open(TEMPLATE_FILE, encoding="utf-8") as f:
        templates = json.load(f)
    # デフォルトテンプレートを常に最新内容で同期
    existing = next((t for t in templates if t["name"] == DEFAULT_TEMPLATE["name"]), None)
    if existing is None:
        templates.insert(0, DEFAULT_TEMPLATE)
        save_templates(templates)
    else:
        # subject と body を最新に更新（ユーザーが手動編集した場合は上書きしない）
        existing.setdefault("subject", DEFAULT_TEMPLATE["subject"])
        existing.setdefault("body",    DEFAULT_TEMPLATE["body"])
    return templates


def save_templates(templates: list[dict]) -> None:
    with open(TEMPLATE_FILE, "w", encoding="utf-8") as f:
        json.dump(templates, f, ensure_ascii=False, indent=2)


# ══════════════════════════════════════════
#  毎日の送信進捗管理
# ══════════════════════════════════════════
def load_daily_config() -> dict:
    """
    {
      "start_index": 4999,   # CSV上の0始まりインデックス（5000番目 = index 4999）
      "daily_count": 20,     # 1日の送信件数
      "last_date": "2026-04-01"  # 最後に「今日の宛先」を生成した日付
    }
    """
    default = {"start_index": 4999, "daily_count": 20, "last_date": ""}
    if not os.path.exists(DAILY_CFG_FILE):
        save_daily_config(default)
        return default
    with open(DAILY_CFG_FILE, encoding="utf-8") as f:
        cfg = json.load(f)
    for k, v in default.items():
        cfg.setdefault(k, v)
    return cfg


def save_daily_config(cfg: dict) -> None:
    with open(DAILY_CFG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ══════════════════════════════════════════
#  送信済みログ管理
# ══════════════════════════════════════════
def load_sent_log() -> set:
    """送信済みメールアドレスの集合を返す"""
    if not os.path.exists(SENT_LOG_FILE):
        return set()
    with open(SENT_LOG_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return set(data.get("sent_emails", []))


def save_sent_log(sent_set: set) -> None:
    """送信済みセットをファイルへ保存"""
    with open(SENT_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump({"sent_emails": sorted(sent_set)}, f, ensure_ascii=False, indent=2)


# ══════════════════════════════════════════
#  CSV 読み込み
# ══════════════════════════════════════════
def load_users() -> list[dict]:
    users = []
    with open(CSV_FILE, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("deleted_at", "").strip():
                continue
            email = row.get("email", "").strip()
            if not email:
                continue
            last_name  = row.get("last_name",  "").strip()
            first_name = row.get("first_name", "").strip()
            full_name  = f"{last_name} {first_name}".strip()
            users.append({
                "id":         row.get("id", ""),
                "name":       full_name if full_name else email,
                "email":      email,
                "last_name":  last_name,
                "first_name": first_name,
            })
    return users


# ══════════════════════════════════════════
#  メール送信（スパム対策強化版）
# ══════════════════════════════════════════
def _plain_to_html(text: str) -> str:
    """プレーンテキストを簡易HTMLに変換（マルチパート用）"""
    escaped = (text
               .replace("&", "&amp;")
               .replace("<", "&lt;")
               .replace(">", "&gt;"))
    paragraphs = "".join(
        f"<p>{line}</p>" if line.strip() else "<br>"
        for line in escaped.splitlines()
    )
    return (
        "<!DOCTYPE html><html><head>"
        "<meta charset='utf-8'>"
        "<style>body{font-family:sans-serif;font-size:14px;color:#222;"
        "line-height:1.7;max-width:640px;margin:0 auto;padding:20px}</style>"
        "</head><body>"
        f"{paragraphs}"
        "</body></html>"
    )


# ══════════════════════════════════════════
#  GitHub Copilot API によるAI言い換え
# ══════════════════════════════════════════
def rewrite_with_ai(subject: str, body: str, recipient_name: str) -> tuple[str, str]:
    """
    GitHub Copilot API（OpenAI互換）を使い、件名・本文を自然に言い換える。
    戻り値: (新しい件名, 新しい本文)
    """
    github_token = os.getenv("GITHUB_TOKEN", "")
    if not github_token:
        raise ValueError(".env に GITHUB_TOKEN を設定してください。")

    client = OpenAI(
        base_url="https://models.inference.ai.azure.com",
        api_key=github_token,
    )

    prompt = (
        "あなたは日本語ビジネスメールの文章校正・言い換えの専門家です。\n"
        "以下のメール件名と本文を、意味・敬語・丁寧さを維持したまま、\n"
        "自然に言い換えてください。\n"
        "スパムフィルターに引っかかりにくくするため、\n"
        "表現のバリエーションを変えながらも誠実なビジネス文として仕上げてください。\n\n"
        f"【宛名】{recipient_name}\n"
        f"【件名】{subject}\n"
        f"【本文】\n{body}\n\n"
        "出力形式（必ずこの形式で出力してください）:\n"
        "SUBJECT: <言い換えた件名>\n"
        "BODY:\n<言い換えた本文>"
    )

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
        max_tokens=1500,
    )

    result_text = response.choices[0].message.content.strip()

    # 出力をパース
    new_subject = subject
    new_body    = body
    if "SUBJECT:" in result_text and "BODY:" in result_text:
        lines = result_text.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("SUBJECT:"):
                new_subject = line[len("SUBJECT:"):].strip()
            elif line.startswith("BODY:"):
                new_body = "\n".join(lines[i + 1:]).strip()
                break

    return new_subject, new_body


def send_email(to_email: str, to_name: str, subject: str, body: str) -> None:
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    from_name = os.getenv("FROM_NAME", "送信者")

    if not smtp_user or not smtp_pass:
        raise ValueError(".env に SMTP_USER と SMTP_PASS を設定してください。")

    # ── 日本語の名前・件名を RFC2047 でエンコード（BCC誤認識を防ぐ）──
    def _encode(text: str) -> str:
        """ASCII以外の文字が含まれていればBase64エンコードする"""
        try:
            text.encode("ascii")
            return text
        except UnicodeEncodeError:
            return Header(text, "utf-8").encode()

    encoded_subject   = _encode(subject)
    encoded_from_name = _encode(from_name)
    encoded_to_name   = _encode(to_name)

    # ── multipart/alternative（テキスト＋HTML両方添付）──
    msg = MIMEMultipart("alternative")
    msg["Subject"]    = encoded_subject
    msg["From"]       = f"{encoded_from_name} <{smtp_user}>"
    msg["To"]         = f"{encoded_to_name} <{to_email}>"   # ← 必ずToヘッダーに明示
    # スパム対策ヘッダー
    msg["Date"]       = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=smtp_user.split("@")[-1])
    msg["X-Mailer"]   = "Microsoft Outlook 16.0"
    # 配信停止ヘッダー（GmailやYahooが正規メールと認識するシグナル）
    msg["List-Unsubscribe"]      = f"<mailto:{smtp_user}?subject=unsubscribe>"
    msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

    # テキストパート（先に添付）
    msg.attach(MIMEText(body, "plain", "utf-8"))
    # HTMLパート（後に添付 → MIMEクライアントはHTMLを優先表示）
    msg.attach(MIMEText(_plain_to_html(body), "html", "utf-8"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(smtp_user, smtp_pass)
        # sendmailの第2引数はSMTPプロトコルの宛先（ヘッダーのToとは別）
        server.sendmail(smtp_user, [to_email], msg.as_string())


# ══════════════════════════════════════════
#  トレイアイコン用画像を生成（外部ファイル不要）
# ══════════════════════════════════════════
def _make_tray_image(size: int = 64) -> Image.Image:
    """封筒風のシンプルアイコンを動的生成"""
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pad  = size // 8
    # 封筒本体
    draw.rectangle([pad, pad * 2, size - pad, size - pad],
                   fill="#0078d7", outline="#004f9a", width=2)
    # 封筒のV字フラップ
    cx = size // 2
    draw.polygon([(pad, pad * 2),
                  (cx, size // 2),
                  (size - pad, pad * 2)],
                 fill="#005fa3")
    return img


# ══════════════════════════════════════════
#  GUI
# ══════════════════════════════════════════
BG      = "#f0f2f5"
ACCENT  = "#0078d7"
GREEN   = "#107c10"
RED     = "#c42b1c"
ORANGE  = "#ca5010"
SENT_COLOR  = "#a0c4a0"   # 送信済み行の背景色
QUEUE_COLOR = "#ffe599"   # キュー待ち行の背景色


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("メール送信ツール")
        self.geometry("1100x780")
        self.minsize(900, 650)
        self.configure(bg=BG)

        self.all_users: list[dict]      = load_users()
        self.selected_users: list[dict] = []
        self.sent_emails: set           = load_sent_log()
        self.templates: list[dict]      = load_templates()   # テンプレート一覧
        self.daily_cfg: dict            = load_daily_config() # 毎日送信設定

        # スケジュール送信状態
        self._schedule_thread: threading.Thread | None = None
        self._schedule_cancel  = threading.Event()
        self._schedule_running = False

        self._filtered_users: list[dict] = []

        # ── トレイアイコン初期化 ──
        self._tray_icon: pystray.Icon | None = None
        self._setup_tray()

        # minimize → トレイに格納
        self.bind("<Unmap>", self._on_unmap)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()

    # ══════════════════════════════════════
    #  トレイアイコン
    # ══════════════════════════════════════
    def _setup_tray(self):
        """pystray アイコンをバックグラウンドスレッドで起動"""
        menu = pystray.Menu(
            pystray.MenuItem("開く", self._tray_show, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("終了", self._tray_quit),
        )
        self._tray_icon = pystray.Icon(
            name="MailSender",
            icon=_make_tray_image(),
            title="メール送信ツール",
            menu=menu,
        )
        t = threading.Thread(target=self._tray_icon.run, daemon=True)
        t.start()

    def _on_unmap(self, event):
        """ウィンドウが最小化されたらトレイに格納"""
        # event.widget がルートウィンドウのときだけ処理
        if event.widget is self:
            self.withdraw()   # タスクバーからも非表示

    def _tray_show(self, icon=None, item=None):
        """トレイアイコンのダブルクリック or「開く」でウィンドウを復元"""
        self.after(0, self._restore_window)

    def _restore_window(self):
        self.deiconify()
        self.state("normal")
        self.lift()
        self.focus_force()

    def _on_close(self):
        """×ボタン：確認してから完全終了"""
        if self._schedule_running:
            if not messagebox.askyesno(
                "終了確認",
                "スケジュール送信が実行中です。終了しますか？"
            ):
                return
            self._schedule_cancel.set()

        if self._tray_icon:
            self._tray_icon.stop()
        self.destroy()

    def _tray_quit(self, icon=None, item=None):
        """トレイメニューの「終了」"""
        if self._tray_icon:
            self._tray_icon.stop()
        self.after(0, self.destroy)

    # ══════════════════════════════════════
    #  UI 構築
    # ══════════════════════════════════════
    def _build_ui(self):
        self._build_top_bar()
        self._build_list_area()
        self._build_manual_input()
        self._build_form()
        self._build_bottom_bar()
        self._filter_users()

    # ── 上部バー（検索 + 凡例） ──
    def _build_top_bar(self):
        top = tk.Frame(self, bg=BG, pady=8, padx=12)
        top.pack(fill="x")

        tk.Label(top, text="🔍", bg=BG, font=("Segoe UI", 12)).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._filter_users())
        tk.Entry(top, textvariable=self.search_var,
                 font=("Segoe UI", 10), width=28,
                 relief="flat", bd=4).pack(side="left", padx=6)

        # 送信済みフィルタ
        self.hide_sent_var = tk.BooleanVar(value=False)
        tk.Checkbutton(top, text="送信済みを非表示",
                       variable=self.hide_sent_var, bg=BG,
                       font=("Segoe UI", 9),
                       command=self._filter_users).pack(side="left", padx=10)

        # 凡例
        for color, label in [(SENT_COLOR, "✅ 送信済み"), (QUEUE_COLOR, "⏳ キュー待ち")]:
            f = tk.Frame(top, bg=color, bd=1, relief="solid")
            f.pack(side="left", padx=4)
            tk.Label(f, text=f" {label} ", bg=color,
                     font=("Segoe UI", 8)).pack()

        self.count_label = tk.Label(top, text="", bg=BG,
                                    font=("Segoe UI", 9), fg="#555")
        self.count_label.pack(side="right")

    # ── 左右リストエリア ──
    def _build_list_area(self):
        mid = tk.Frame(self, bg=BG, padx=10)
        mid.pack(fill="both", expand=True, pady=2)

        # 左：全ユーザーリスト
        left_frame = tk.LabelFrame(mid, text="全ユーザー", bg=BG,
                                   font=("Segoe UI", 9, "bold"), padx=4, pady=4)
        left_frame.pack(side="left", fill="both", expand=True)

        self.user_list = tk.Listbox(
            left_frame, selectmode="extended", font=("Segoe UI", 9),
            activestyle="none",
            selectbackground=ACCENT, selectforeground="white")
        sb_l = ttk.Scrollbar(left_frame, orient="vertical",
                              command=self.user_list.yview)
        self.user_list.configure(yscrollcommand=sb_l.set)
        sb_l.pack(side="right", fill="y")
        self.user_list.pack(fill="both", expand=True)
        self.user_list.bind("<Double-Button-1>", lambda _: self._add_selected())

        # 中央ボタン
        btn_frame = tk.Frame(mid, bg=BG, padx=8)
        btn_frame.pack(side="left", fill="y", pady=50)
        bs = {"font": ("Segoe UI", 9), "width": 10, "bd": 0,
              "relief": "flat", "cursor": "hand2", "pady": 6}
        tk.Button(btn_frame, text="追加 ▶",    bg=ACCENT,  fg="white", command=self._add_selected,  **bs).pack(pady=5)
        tk.Button(btn_frame, text="全追加 ▶▶", bg=ACCENT,  fg="white", command=self._add_all,       **bs).pack(pady=5)
        tk.Button(btn_frame, text="◀ 削除",    bg=RED,     fg="white", command=self._remove_selected,**bs).pack(pady=5)
        tk.Button(btn_frame, text="◀◀ 全削除", bg=RED,     fg="white", command=self._remove_all,    **bs).pack(pady=5)

        # 右：送信先リスト
        right_frame = tk.LabelFrame(mid, text="送信先リスト", bg=BG,
                                    font=("Segoe UI", 9, "bold"), padx=4, pady=4)
        right_frame.pack(side="left", fill="both", expand=True)

        self.dest_list = tk.Listbox(
            right_frame, selectmode="extended", font=("Segoe UI", 9),
            activestyle="none",
            selectbackground=GREEN, selectforeground="white")
        sb_r = ttk.Scrollbar(right_frame, orient="vertical",
                              command=self.dest_list.yview)
        self.dest_list.configure(yscrollcommand=sb_r.set)
        sb_r.pack(side="right", fill="y")
        self.dest_list.pack(fill="both", expand=True)
        self.dest_list.bind("<Double-Button-1>", lambda _: self._remove_selected())

    # ── 手動メールアドレス入力エリア ──
    def _build_manual_input(self):
        frame = tk.LabelFrame(self, text="📧 メールアドレスを直接入力して追加",
                              bg=BG, font=("Segoe UI", 9, "bold"), padx=10, pady=6)
        frame.pack(fill="x", padx=10, pady=2)

        row = tk.Frame(frame, bg=BG)
        row.pack(fill="x")

        tk.Label(row, text="名前（任意）:", bg=BG, font=("Segoe UI", 9)).pack(side="left")
        self.manual_name_var = tk.StringVar()
        tk.Entry(row, textvariable=self.manual_name_var,
                 font=("Segoe UI", 10), width=16,
                 relief="flat", bd=3).pack(side="left", padx=(4, 12))

        tk.Label(row, text="メールアドレス:", bg=BG, font=("Segoe UI", 9)).pack(side="left")
        self.manual_email_var = tk.StringVar()
        self.manual_email_entry = tk.Entry(
            row, textvariable=self.manual_email_var,
            font=("Segoe UI", 10), width=32,
            relief="flat", bd=3)
        self.manual_email_entry.pack(side="left", padx=(4, 12))
        self.manual_email_entry.bind("<Return>", lambda _: self._add_manual_email())

        tk.Button(row, text="送信先に追加",
                  bg=ORANGE, fg="white", bd=0, relief="flat",
                  font=("Segoe UI", 9), cursor="hand2", pady=4, padx=8,
                  command=self._add_manual_email).pack(side="left")

        tk.Label(row, text="  ※ 複数はカンマ区切りで入力可",
                 bg=BG, font=("Segoe UI", 8), fg="#777").pack(side="left")

    # ── メール内容フォーム ──
    def _build_form(self):
        form = tk.LabelFrame(self, text="メール内容", bg=BG,
                             font=("Segoe UI", 9, "bold"), padx=10, pady=6)
        form.pack(fill="x", padx=10, pady=2)

        # ── テンプレート選択行 ──
        tmpl_row = tk.Frame(form, bg=BG)
        tmpl_row.pack(fill="x", pady=(0, 4))

        tk.Label(tmpl_row, text="テンプレート:", bg=BG,
                 font=("Segoe UI", 9), width=10, anchor="w").pack(side="left")

        self.template_var = tk.StringVar()
        self.template_combo = ttk.Combobox(
            tmpl_row, textvariable=self.template_var,
            font=("Segoe UI", 9), width=32, state="readonly")
        self.template_combo.pack(side="left", padx=(0, 6))
        self.template_combo.bind("<<ComboboxSelected>>", lambda _: self._load_template())

        btn_s = {"bd": 0, "relief": "flat", "cursor": "hand2",
                 "font": ("Segoe UI", 9), "padx": 8, "pady": 3}
        tk.Button(tmpl_row, text="💾 保存", bg=ACCENT, fg="white",
                  command=self._save_template, **btn_s).pack(side="left", padx=2)
        tk.Button(tmpl_row, text="✏️ 上書き", bg=ORANGE, fg="white",
                  command=self._overwrite_template, **btn_s).pack(side="left", padx=2)
        tk.Button(tmpl_row, text="🗑 削除", bg=RED, fg="white",
                  command=self._delete_template, **btn_s).pack(side="left", padx=2)

        # ── 件名 ──
        sr = tk.Frame(form, bg=BG)
        sr.pack(fill="x", pady=2)
        tk.Label(sr, text="件名：", bg=BG, font=("Segoe UI", 10),
                 width=8, anchor="w").pack(side="left")
        self.subject_var = tk.StringVar()
        tk.Entry(sr, textvariable=self.subject_var,
                 font=("Segoe UI", 10), relief="flat", bd=3).pack(
            side="left", fill="x", expand=True)

        # ── 本文 ──
        br = tk.Frame(form, bg=BG)
        br.pack(fill="x", pady=2)
        tk.Label(br, text="本文：", bg=BG, font=("Segoe UI", 10),
                 width=8, anchor="nw").pack(side="left", anchor="n")
        self.body_text = scrolledtext.ScrolledText(
            br, height=6, font=("Segoe UI", 10), wrap="word", relief="flat", bd=3)
        self.body_text.pack(side="left", fill="both", expand=True)

        tk.Label(form,
                 text="💡 本文中の {name} は宛名に自動置換されます。",
                 bg=BG, font=("Segoe UI", 8), fg="#555").pack(anchor="w")

        # ── AI言い換えオプション ──
        ai_row = tk.Frame(form, bg=BG)
        ai_row.pack(fill="x", pady=(4, 0))

        self.ai_rewrite_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            ai_row, text="🤖 GitHub Copilot API で送信ごとに本文を自然に言い換える",
            variable=self.ai_rewrite_var,
            bg=BG, font=("Segoe UI", 9),
        ).pack(side="left")
        tk.Label(
            ai_row,
            text="（GITHUB_TOKEN が .env に必要）",
            bg=BG, font=("Segoe UI", 8), fg="#888",
        ).pack(side="left", padx=6)

        # テンプレート一覧を初期表示
        self._refresh_template_combo()

    # ── テンプレート操作 ──
    def _refresh_template_combo(self):
        names = [t["name"] for t in self.templates]
        self.template_combo["values"] = names
        if names and not self.template_var.get():
            self.template_combo.current(0)
            self._load_template()

    def _load_template(self):
        name = self.template_var.get()
        for t in self.templates:
            if t["name"] == name:
                self.subject_var.set(t["subject"])
                self.body_text.delete("1.0", "end")
                self.body_text.insert("1.0", t["body"])
                break

    def _save_template(self):
        subject = self.subject_var.get().strip()
        body    = self.body_text.get("1.0", "end").strip()
        if not subject and not body:
            messagebox.showwarning("保存エラー", "件名または本文を入力してください。")
            return

        # テンプレート名をダイアログで入力
        dialog = _InputDialog(self, title="テンプレートを保存",
                              prompt="テンプレート名を入力してください：",
                              initial=subject[:20] if subject else "")
        name = dialog.result
        if not name:
            return

        # 同名があれば上書き確認
        existing = next((t for t in self.templates if t["name"] == name), None)
        if existing:
            if not messagebox.askyesno("上書き確認",
                                       f"「{name}」はすでに存在します。上書きしますか？"):
                return
            existing["subject"] = subject
            existing["body"]    = body
        else:
            self.templates.append({"name": name, "subject": subject, "body": body})

        save_templates(self.templates)
        self._refresh_template_combo()
        self.template_var.set(name)
        self.status_var.set(f"💾 テンプレート「{name}」を保存しました。")

    def _overwrite_template(self):
        name = self.template_var.get()
        if not name:
            messagebox.showwarning("エラー", "上書きするテンプレートを選択してください。")
            return
        subject = self.subject_var.get().strip()
        body    = self.body_text.get("1.0", "end").strip()
        for t in self.templates:
            if t["name"] == name:
                t["subject"] = subject
                t["body"]    = body
                break
        save_templates(self.templates)
        self.status_var.set(f"✏️ テンプレート「{name}」を上書き保存しました。")

    def _delete_template(self):
        name = self.template_var.get()
        if not name:
            messagebox.showwarning("エラー", "削除するテンプレートを選択してください。")
            return
        if not messagebox.askyesno("削除確認", f"「{name}」を削除しますか？"):
            return
        self.templates = [t for t in self.templates if t["name"] != name]
        save_templates(self.templates)
        self.template_var.set("")
        self._refresh_template_combo()
        self.status_var.set(f"🗑 テンプレート「{name}」を削除しました。")

    # ── 下部バー（スケジュール設定 + 送信ボタン） ──
    def _build_bottom_bar(self):
        bar = tk.Frame(self, bg=BG, padx=12, pady=6)
        bar.pack(fill="x")

        # ── 毎日自動選択エリア ──
        daily_frame = tk.LabelFrame(bar, text="📅 毎日自動選択（送信済みスキップ）",
                                    bg=BG, font=("Segoe UI", 9, "bold"),
                                    padx=8, pady=4)
        daily_frame.pack(side="left", padx=(0, 10))

        tk.Label(daily_frame, text="開始番号:", bg=BG,
                 font=("Segoe UI", 9)).pack(side="left")
        self.start_index_var = tk.IntVar(value=self.daily_cfg.get("start_index", 4999) + 1)
        tk.Spinbox(daily_frame, from_=1, to=99999,
                   textvariable=self.start_index_var,
                   width=6, font=("Segoe UI", 9)).pack(side="left", padx=(2, 8))

        tk.Label(daily_frame, text="件数:", bg=BG,
                 font=("Segoe UI", 9)).pack(side="left")
        self.daily_count_var = tk.IntVar(value=self.daily_cfg.get("daily_count", 20))
        tk.Spinbox(daily_frame, from_=1, to=200,
                   textvariable=self.daily_count_var,
                   width=4, font=("Segoe UI", 9)).pack(side="left", padx=(2, 8))

        tk.Button(daily_frame, text="📋 今日の宛先を選択",
                  bg="#6b4fbb", fg="white", bd=0, relief="flat",
                  font=("Segoe UI", 9), cursor="hand2", padx=8, pady=3,
                  command=self._select_daily_users).pack(side="left")

        # ── スケジュール設定 ──
        sched_frame = tk.LabelFrame(bar, text="⏱ 送信間隔（ランダム）",
                                    bg=BG, font=("Segoe UI", 9, "bold"),
                                    padx=8, pady=4)
        sched_frame.pack(side="left")

        self.schedule_var = tk.BooleanVar(value=False)
        tk.Checkbutton(sched_frame, text="有効", variable=self.schedule_var,
                       bg=BG, font=("Segoe UI", 9),
                       command=self._toggle_schedule_ui).pack(side="left")

        tk.Label(sched_frame, text="最小:", bg=BG,
                 font=("Segoe UI", 9)).pack(side="left", padx=(10, 2))
        self.min_interval_var = tk.IntVar(value=20)
        self.min_spin = tk.Spinbox(sched_frame, from_=1, to=120,
                                   textvariable=self.min_interval_var,
                                   width=4, font=("Segoe UI", 9), state="disabled")
        self.min_spin.pack(side="left")
        tk.Label(sched_frame, text="分  最大:", bg=BG,
                 font=("Segoe UI", 9)).pack(side="left", padx=(2, 2))
        self.max_interval_var = tk.IntVar(value=40)
        self.max_spin = tk.Spinbox(sched_frame, from_=1, to=120,
                                   textvariable=self.max_interval_var,
                                   width=4, font=("Segoe UI", 9), state="disabled")
        self.max_spin.pack(side="left")
        tk.Label(sched_frame, text="分", bg=BG, font=("Segoe UI", 9)).pack(side="left", padx=2)

        # キャンセルボタン（隠し）
        self.cancel_btn = tk.Button(sched_frame, text="⛔ 中止",
                                    bg=RED, fg="white", bd=0, relief="flat",
                                    font=("Segoe UI", 9), cursor="hand2", padx=6,
                                    command=self._cancel_schedule)
        # 送信ボタン
        self.send_btn = tk.Button(bar, text="  ✉ 送信開始  ",
                                  font=("Segoe UI", 11, "bold"),
                                  bg=GREEN, fg="white",
                                  bd=0, relief="flat", cursor="hand2", pady=8,
                                  command=self._on_send)
        self.send_btn.pack(side="right", padx=10)

        # ステータスバー
        self.status_var = tk.StringVar(value="準備完了")
        tk.Label(bar, textvariable=self.status_var, bg=BG,
                 font=("Segoe UI", 9), fg="#333").pack(side="left", padx=12)

    # ══════════════════════════════════════
    #  ユーザーリスト操作
    # ══════════════════════════════════════
    def _filter_users(self):
        keyword   = self.search_var.get().lower()
        hide_sent = self.hide_sent_var.get()
        dest_emails = {u["email"] for u in self.selected_users}

        filtered = []
        for u in self.all_users:
            if hide_sent and u["email"] in self.sent_emails:
                continue
            if keyword and keyword not in u["name"].lower() \
                       and keyword not in u["email"].lower():
                continue
            filtered.append(u)

        self.user_list.delete(0, "end")
        for u in filtered:
            if u["email"] in self.sent_emails:
                badge = "✅"
            elif u["email"] in dest_emails:
                badge = "📨"
            else:
                badge = "   "
            label = f"{badge} {u['name']}  <{u['email']}>"
            self.user_list.insert("end", label)
            # 送信済み色付け
            idx = self.user_list.size() - 1
            if u["email"] in self.sent_emails:
                self.user_list.itemconfig(idx, bg=SENT_COLOR)
            elif u["email"] in dest_emails:
                self.user_list.itemconfig(idx, bg=QUEUE_COLOR)

        self._filtered_users = filtered
        self.count_label.config(
            text=f"表示: {len(filtered)} / 全 {len(self.all_users)} 件  "
                 f"（送信済 {len(self.sent_emails)} 件）")

    def _add_selected(self):
        for idx in self.user_list.curselection():
            u = self._filtered_users[idx]
            if u not in self.selected_users:
                self.selected_users.append(u)
        self._refresh_dest_list()
        self._filter_users()

    def _add_all(self):
        for u in self._filtered_users:
            if u not in self.selected_users:
                self.selected_users.append(u)
        self._refresh_dest_list()
        self._filter_users()

    def _remove_selected(self):
        for idx in reversed(self.dest_list.curselection()):
            del self.selected_users[idx]
        self._refresh_dest_list()
        self._filter_users()

    def _remove_all(self):
        self.selected_users.clear()
        self._refresh_dest_list()
        self._filter_users()

    def _refresh_dest_list(self):
        self.dest_list.delete(0, "end")
        for u in self.selected_users:
            sent_mark = "✅ " if u["email"] in self.sent_emails else ""
            self.dest_list.insert("end", f"{sent_mark}{u['name']}  <{u['email']}>")
            if u["email"] in self.sent_emails:
                self.dest_list.itemconfig(self.dest_list.size() - 1, bg=SENT_COLOR)

    # ── 手動メールアドレス追加 ──
    def _add_manual_email(self):
        raw_emails = self.manual_email_var.get().strip()
        raw_name   = self.manual_name_var.get().strip()
        if not raw_emails:
            messagebox.showwarning("入力エラー", "メールアドレスを入力してください。")
            return

        email_pattern = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
        entries = [e.strip() for e in raw_emails.split(",") if e.strip()]
        added, invalid = [], []

        for email in entries:
            if not email_pattern.match(email):
                invalid.append(email)
                continue
            name = raw_name if (raw_name and len(entries) == 1) else email
            user = {"id": "manual", "name": name, "email": email,
                    "last_name": "", "first_name": ""}
            # 重複チェック
            if not any(u["email"] == email for u in self.selected_users):
                self.selected_users.append(user)
                added.append(email)

        if invalid:
            messagebox.showwarning("無効なアドレス",
                                   "以下は無効なメールアドレスです：\n" + "\n".join(invalid))
        if added:
            self.manual_email_var.set("")
            self.manual_name_var.set("")
            self._refresh_dest_list()
            self._filter_users()

    # ══════════════════════════════════════
    #  毎日自動選択
    # ══════════════════════════════════════
    def _select_daily_users(self):
        """
        送信済みをスキップしながら、指定開始番号から daily_count 件を
        送信先リストにセットする。先頭に固定宛先 sunny を追加する。
        """
        count       = self.daily_count_var.get()
        start_1idx  = self.start_index_var.get()          # 1始まり番号
        start_0idx  = max(0, start_1idx - 1)              # 0始まりインデックス

        # 固定宛先（sunny）
        fixed = FIXED_DAILY_USER.copy()
        selected: list[dict] = [fixed]

        # CSV から送信済みスキップしつつ count 件ピック
        picked = 0
        next_start = start_0idx
        for i in range(start_0idx, len(self.all_users)):
            if picked >= count:
                next_start = i
                break
            u = self.all_users[i]
            if u["email"] in self.sent_emails:
                continue
            selected.append(u)
            picked += 1
        else:
            next_start = len(self.all_users)

        self.selected_users = selected
        self._refresh_dest_list()
        self._filter_users()

        # 設定を保存（次回起動時に続きから）
        self.daily_cfg["start_index"]  = next_start
        self.daily_cfg["daily_count"]  = count
        self.daily_cfg["last_date"]    = datetime.now().strftime("%Y-%m-%d")
        save_daily_config(self.daily_cfg)
        # 次回用に表示も更新
        self.start_index_var.set(next_start + 1)

        self.status_var.set(
            f"📋 今日の宛先を選択しました："
            f"sunny (固定) + {picked} 件（{start_1idx}〜{next_start} 番）"
        )

    # ══════════════════════════════════════
    #  スケジュール UI 制御
    # ══════════════════════════════════════
    def _toggle_schedule_ui(self):
        state = "normal" if self.schedule_var.get() else "disabled"
        self.min_spin.config(state=state)
        self.max_spin.config(state=state)

    # ══════════════════════════════════════
    #  送信処理
    # ══════════════════════════════════════
    def _on_send(self):
        if not self.selected_users:
            messagebox.showwarning("警告", "送信先が選択されていません。")
            return

        subject = self.subject_var.get().strip()
        body    = self.body_text.get("1.0", "end").strip()

        if not subject:
            messagebox.showwarning("警告", "件名を入力してください。")
            return
        if not body:
            messagebox.showwarning("警告", "本文を入力してください。")
            return

        use_schedule = self.schedule_var.get()
        count        = len(self.selected_users)

        if use_schedule:
            min_m = self.min_interval_var.get()
            max_m = self.max_interval_var.get()
            if min_m >= max_m:
                messagebox.showwarning("設定エラー", "最小間隔は最大間隔より小さくしてください。")
                return
            confirm = messagebox.askyesno(
                "スケジュール送信確認",
                f"{count} 名に {min_m}〜{max_m} 分のランダム間隔で送信します。\n\n"
                f"件名: {subject}\n\n開始しますか？"
            )
            if not confirm:
                return
            self._start_schedule_send(subject, body, min_m, max_m)
        else:
            confirm = messagebox.askyesno(
                "送信確認",
                f"{count} 名に送信しますか？\n\n件名: {subject}"
            )
            if not confirm:
                return
            self._send_immediately(subject, body)

    def _send_immediately(self, subject: str, body: str):
        """即時一括送信"""
        use_ai   = self.ai_rewrite_var.get()
        success, failed = 0, []
        for user in list(self.selected_users):
            personal_body = body.replace("{name}", user["name"])
            send_subject  = subject
            # AI言い換え
            if use_ai:
                try:
                    send_subject, personal_body = rewrite_with_ai(
                        subject, personal_body, user["name"])
                except Exception as e:
                    self.status_var.set(f"⚠️ AI言い換え失敗（元の本文を使用）: {e}")
            try:
                send_email(user["email"], user["name"], send_subject, personal_body)
                self.sent_emails.add(user["email"])
                success += 1
            except Exception as e:
                failed.append(f"{user['email']}: {e}")

        save_sent_log(self.sent_emails)
        self._refresh_dest_list()
        self._filter_users()

        msg = f"✅ 送信成功: {success} 件"
        if failed:
            msg += f"\n❌ 失敗: {len(failed)} 件\n\n" + "\n".join(failed)
        messagebox.showinfo("送信結果", msg)

    def _start_schedule_send(self, subject: str, body: str,
                              min_min: int, max_min: int):
        """スケジュール送信をバックグラウンドスレッドで開始"""
        self._schedule_cancel.clear()
        self._schedule_running = True
        self.send_btn.config(state="disabled")
        self.cancel_btn.pack(side="left", padx=8)

        queue  = list(self.selected_users)
        use_ai = self.ai_rewrite_var.get()

        def worker():
            for i, user in enumerate(queue):
                if self._schedule_cancel.is_set():
                    self._ui_call(lambda: self._on_schedule_done(
                        i, len(queue), cancelled=True))
                    return

                personal_body = body.replace("{name}", user["name"])
                send_subject  = subject
                # AI言い換え
                if use_ai:
                    try:
                        send_subject, personal_body = rewrite_with_ai(
                            subject, personal_body, user["name"])
                    except Exception as e:
                        self._ui_call(lambda err=e: self._update_status(
                            f"⚠️ AI言い換え失敗（元の本文を使用）: {err}"))
                try:
                    send_email(user["email"], user["name"], send_subject, personal_body)
                    self.sent_emails.add(user["email"])
                    save_sent_log(self.sent_emails)
                    msg = (f"✅ [{i+1}/{len(queue)}] {user['name']} "
                           f"<{user['email']}> に送信完了")
                except Exception as e:
                    msg = (f"❌ [{i+1}/{len(queue)}] {user['email']} "
                           f"失敗: {e}")

                self._ui_call(lambda m=msg: self._update_status(m))
                self._ui_call(lambda: (self._refresh_dest_list(), self._filter_users()))

                # 最後の1件は待機不要
                if i < len(queue) - 1 and not self._schedule_cancel.is_set():
                    wait_sec = random.randint(min_min * 60, max_min * 60)
                    next_time = datetime.now().strftime("%H:%M")
                    self._ui_call(lambda s=wait_sec, nt=next_time:
                                  self._update_status(
                                      f"⏳ 次の送信まで {s//60} 分 {s%60} 秒 待機中…"
                                      f"（{nt} 開始）"))
                    # 1秒ごとにキャンセルチェック
                    for _ in range(wait_sec):
                        if self._schedule_cancel.is_set():
                            break
                        time.sleep(1)

            self._ui_call(lambda: self._on_schedule_done(len(queue), len(queue)))

        self._schedule_thread = threading.Thread(target=worker, daemon=True)
        self._schedule_thread.start()

    def _update_status(self, msg: str):
        self.status_var.set(msg)

    def _on_schedule_done(self, sent: int, total: int, cancelled: bool = False):
        self._schedule_running = False
        self.send_btn.config(state="normal")
        self.cancel_btn.pack_forget()
        self._refresh_dest_list()
        self._filter_users()

        if cancelled:
            self.status_var.set(f"⛔ 中止（{sent}/{total} 件送信済み）")
            messagebox.showinfo("中止", f"スケジュール送信を中止しました。\n送信済み: {sent} 件")
        else:
            self.status_var.set(f"✅ スケジュール送信完了（{sent} 件）")
            messagebox.showinfo("完了", f"スケジュール送信が完了しました。\n送信: {sent} 件")

    def _cancel_schedule(self):
        if messagebox.askyesno("中止確認", "スケジュール送信を中止しますか？"):
            self._schedule_cancel.set()

    def _ui_call(self, fn):
        """スレッドから安全に UI を更新"""
        self.after(0, fn)


# ══════════════════════════════════════════
#  テンプレート名入力ダイアログ
# ══════════════════════════════════════════
class _InputDialog(tk.Toplevel):
    def __init__(self, parent, title: str, prompt: str, initial: str = ""):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()
        self.result: str | None = None

        self.configure(bg=BG, padx=20, pady=16)
        tk.Label(self, text=prompt, bg=BG,
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 6))

        self._var = tk.StringVar(value=initial)
        entry = tk.Entry(self, textvariable=self._var,
                         font=("Segoe UI", 10), width=34,
                         relief="flat", bd=3)
        entry.pack(fill="x")
        entry.select_range(0, "end")
        entry.focus_set()
        entry.bind("<Return>", lambda _: self._ok())

        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(pady=(12, 0))
        bs = {"bd": 0, "relief": "flat", "cursor": "hand2",
              "font": ("Segoe UI", 9), "padx": 16, "pady": 5}
        tk.Button(btn_row, text="OK",     bg=GREEN, fg="white",
                  command=self._ok,     **bs).pack(side="left", padx=4)
        tk.Button(btn_row, text="キャンセル", bg="#888", fg="white",
                  command=self.destroy, **bs).pack(side="left", padx=4)

        # 画面中央に配置
        self.update_idletasks()
        px = parent.winfo_x() + parent.winfo_width()  // 2 - self.winfo_width()  // 2
        py = parent.winfo_y() + parent.winfo_height() // 2 - self.winfo_height() // 2
        self.geometry(f"+{px}+{py}")
        self.wait_window()

    def _ok(self):
        self.result = self._var.get().strip()
        self.destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()
