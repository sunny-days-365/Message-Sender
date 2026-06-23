# メール送信ツール (Message Sender)

[日本語](#日本語) | [English](#english)

---

## 日本語

CSV で管理した宛先リストから、テンプレートを使って一括・スケジュール送信できる Windows 向けデスクトップアプリです。送信済みの記録、毎日の自動宛先選択、GitHub Copilot API による本文の言い換えにも対応しています。

### 主な機能

- **宛先管理** — `users.csv` からユーザーを読み込み、検索・フィルタ・手動追加が可能
- **送信済みトラッキング** — 送信済みアドレスを記録し、重複送信を防止
- **メールテンプレート** — 件名・本文の保存・読み込み・上書き・削除（`{name}` で宛名を自動置換）
- **即時送信 / スケジュール送信** — ランダム間隔（分単位）で順次送信
- **毎日自動選択** — 開始番号と件数を指定し、送信済みをスキップしながら当日分の宛先を自動セット
- **AI 言い換え** — GitHub Copilot API（OpenAI 互換）で送信ごとに件名・本文を自然に言い換え
- **システムトレイ** — 最小化時にトレイへ格納し、バックグラウンドでスケジュール送信を継続

### 必要環境

- Windows 10 以降
- Python 3.10 以上（ソースから実行する場合）
- 送信に使うメールアカウント（Gmail 推奨）と SMTP 用アプリパスワード

### 初回セットアップに必要なもの

リポジトリにはソースコードとサンプルファイルのみ含まれます。動かす前に、次を用意してください。

| 項目 | 必須 | 説明 |
|------|------|------|
| `.env` | ✓ | SMTP 認証情報。`.env.example` をコピーして作成 |
| `users.csv` | ✓ | 宛先リスト。`users.csv.example` をコピーし、実データに差し替え |
| Python パッケージ | ✓ | `pip install -r requirements.txt` |
| Gmail アプリパスワード | ✓* | Gmail 利用時は必須（通常のログインパスワードは不可） |
| `GITHUB_TOKEN` | — | AI 言い換えを使う場合のみ `.env` に追加 |

> `.env` と `users.csv` は個人情報・認証情報を含むため **Git に含まれていません**。各自の PC で作成してください。

初回起動時に自動作成されるファイル（手動作成不要）:

- `mail_templates.json` — 保存したメールテンプレート
- `sent_log.json` — 送信済みアドレスの記録
- `daily_config.json` — 毎日自動選択の進捗

### リポジトリからのセットアップ

```bash
git clone https://github.com/sunny-days-365/Message-Sender.git
cd Message-Sender
pip install -r requirements.txt
copy .env.example .env
copy users.csv.example users.csv
```

その後、`.env` に SMTP 設定を記入し、`users.csv` を実際の宛先データに更新してから起動します。

```bash
python main.py
```

### セットアップ

#### 1. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

EXE をビルドする場合は PyInstaller も必要です。

```bash
pip install pyinstaller
```

#### 2. メールアカウント設定（`.env`）

このアプリには画面上の「SMTP 設定」入力欄はありません。送信に使うメールアカウントの情報は、プロジェクトフォルダ（または EXE と同じフォルダ）の **`.env` ファイル** に書きます。

##### Gmail を使う場合（推奨手順）

1. **Google アカウントで 2 段階認証を有効にする**
   - [Google アカウント](https://myaccount.google.com/) → **セキュリティ** → **2 段階認証プロセス** をオンにする

2. **アプリパスワードを作成する**
   - 同じ **セキュリティ** ページ → **2 段階認証プロセス** の下にある **アプリパスワード**
   - アプリを「メール」、デバイスを「Windows パソコン」などに設定
   - 表示された **16 文字のパスワード** をコピーする（通常の Gmail ログインパスワードは使えません）

3. **`.env` ファイルを作成する**

   プロジェクトルート（`main.py` と同じ場所）で、同梱の `.env.example` をコピーして `.env` を作成し、値を自分の情報に書き換えます。

   ```bash
   copy .env.example .env
   ```

   `.env` の例:

   ```env
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=your-email@gmail.com
   SMTP_PASS=xxxx xxxx xxxx xxxx
   FROM_NAME=Alexandra
   ```

   | 変数 | 必須 | 説明 |
   |------|------|------|
   | `SMTP_HOST` | — | SMTP サーバー（Gmail は `smtp.gmail.com`） |
   | `SMTP_PORT` | — | SMTP ポート（Gmail は `587`） |
   | `SMTP_USER` | ✓ | 送信元の Gmail アドレス |
   | `SMTP_PASS` | ✓ | 上で作成したアプリパスワード |
   | `FROM_NAME` | — | 受信者に表示される送信者名 |

4. **動作確認**
   - アプリを起動し、自分宛に 1 通テスト送信する
   - エラーが出る場合は `.env` のスペルミス、2 段階認証、アプリパスワードの再作成を確認する

##### その他のメールプロバイダー

| プロバイダー | `SMTP_HOST` | `SMTP_PORT` |
|-------------|-------------|-------------|
| Gmail | `smtp.gmail.com` | `587` |
| Outlook / Hotmail | `smtp-mail.outlook.com` | `587` |
| Yahoo! メール（日本） | `smtp.mail.yahoo.co.jp` | `587` |

各プロバイダーでも、多くの場合はアプリ専用パスワードまたは SMTP 認証の有効化が必要です。公式ヘルプを参照してください。

##### AI 言い換え（任意）

GitHub Copilot API で送信ごとに本文を言い換える場合は、`.env` に次を追加します。

```env
GITHUB_TOKEN=your-github-token
```

| 変数 | 必須 | 説明 |
|------|------|------|
| `GITHUB_TOKEN` | — | [GitHub Settings → Developer settings → Personal access tokens](https://github.com/settings/tokens) で発行したトークン |

> **注意:** `.env` には認証情報が含まれます。リポジトリにコミットしないでください。

#### 3. 宛先リスト（`users.csv`）

`users.csv` はリポジトリに含まれていません。`users.csv.example` をコピーして作成してください。

```bash
copy users.csv.example users.csv
```

その後、実際の宛先データで上書きするか、エクスポートした CSV を配置します。

| カラム | 説明 |
|--------|------|
| `id` | ユーザー ID |
| `last_name` | 姓 |
| `first_name` | 名 |
| `email` | メールアドレス |
| `deleted_at` | 削除日時（値がある行はスキップ） |

表示名は `姓 名` を結合して使用します。名前が空の場合はメールアドレスが宛名になります。

### 起動方法

**Python から実行:**

```bash
python main.py
```

VS Code ではタスク **「メール送信ツール 起動」** でも起動できます。

**EXE から実行:** ビルド後、`dist/MessageSender.exe` を実行します。`.env` は EXE と同じフォルダに置いてください。

### EXE のビルド

```bash
pyinstaller build_exe.spec
```

配布時は EXE と同じフォルダに `.env` と `users.csv` を置きます。`mail_templates.json`、`sent_log.json`、`daily_config.json` は初回起動時に自動作成されます。

### 使い方

#### 画面上の「メール内容」エリアの設定

ウィンドウ中央付近の **「メール内容」** ボックスで、送信するメールの内容を設定します。

| UI 要素 | 説明 |
|---------|------|
| **テンプレート**（ドロップダウン） | 保存済みテンプレートを選択すると、件名・本文が自動で読み込まれます |
| **💾 保存** | 現在の件名・本文を新しい名前でテンプレートとして保存 |
| **✏️ 上書き** | 選択中のテンプレートを現在の件名・本文で更新 |
| **🗑 削除** | 選択中のテンプレートを削除 |
| **件名** | 送信メールの件名 |
| **本文** | 送信メールの本文。`{name}` は各宛先の名前に自動置換されます |
| **🤖 AI 言い換え**（チェックボックス） | オンにすると、送信ごとに GitHub Copilot API で件名・本文を言い換えてから送信 |

**設定の流れ（例）:**

1. テンプレートを選ぶ、または件名・本文を直接入力する
2. 本文に `{name}様` のように宛名プレースホルダーを入れる
3. よく使う内容なら **保存** でテンプレート化する
4. 宛先を選び、**送信開始** をクリックする

#### 基本的な送信フロー

1. 左の「全ユーザー」リストから宛先を選び、**追加 ▶** で送信先リストへ移動
2. 「メール内容」で件名・本文を設定
3. **送信開始** をクリックして確認ダイアログで送信

#### 毎日自動選択

1. **開始番号** — CSV 上の何番目から選ぶか（1 始まり）
2. **件数** — 1 日に送る件数
3. **今日の宛先を選択** — 送信済みをスキップしながら宛先をセット

固定宛先が先頭に 1 件追加されます。進捗は `daily_config.json` に保存されます。

#### スケジュール送信

**送信間隔（ランダム）** を有効にすると、各メールの間に指定した最小〜最大分のランダム待機が入ります。送信中は **中止** でキャンセルできます。最小化するとシステムトレイに格納され、送信は継続します。

### ファイル構成

```
Message-Sender/
├── main.py              # アプリケーション本体
├── requirements.txt     # Python 依存パッケージ
├── build_exe.spec       # PyInstaller ビルド設定
├── README.md
├── .env.example         # SMTP 設定のサンプル（→ .env にコピー）
├── users.csv.example    # 宛先 CSV のサンプル（→ users.csv にコピー）
├── .env                 # SMTP / API 認証情報（要作成・Git 除外）
├── users.csv            # 宛先リスト（要作成・Git 除外）
├── mail_templates.json  # 保存済みテンプレート（自動生成）
├── sent_log.json        # 送信済みアドレスログ（自動生成）
└── daily_config.json    # 毎日送信の進捗（自動生成）
```

### 技術スタック

- **GUI:** Tkinter
- **メール:** smtplib（multipart/alternative、日本語ヘッダー対応）
- **トレイ:** pystray + Pillow
- **設定:** python-dotenv
- **AI:** OpenAI SDK（GitHub Models API 経由）
- **パッケージング:** PyInstaller

### 注意事項

- 大量送信やスパム行為は各メールプロバイダーの利用規約や法令に違反する可能性があります。宛先の同意取得と適切な送信頻度を守ってください。
- Gmail では通常のログインパスワードではなく **アプリパスワード** が必要です。
- `users.csv` には個人情報が含まれるため、取り扱いと保管に注意してください。

---

## English

A Windows desktop app for bulk and scheduled email sending from a CSV recipient list. It supports sent-mail tracking, daily auto-selection of recipients, and optional AI-powered message rewriting via the GitHub Copilot API.

### Features

- **Recipient management** — Load users from `users.csv`, search, filter, and add addresses manually
- **Sent tracking** — Log sent addresses to avoid duplicates
- **Email templates** — Save, load, overwrite, and delete subject/body templates (`{name}` is replaced per recipient)
- **Immediate / scheduled sending** — Send in sequence with random minute-based intervals
- **Daily auto-selection** — Pick today's batch from a start index, skipping already-sent addresses
- **AI rewriting** — Optionally rephrase subject and body per recipient via GitHub Copilot API
- **System tray** — Minimize to tray; scheduled sending continues in the background

### Requirements

- Windows 10 or later
- Python 3.10+ (when running from source)
- A mail account for sending (Gmail recommended) with an SMTP app password

### What you need before first run

The repository ships source code and sample files only. Prepare the following before running the app.

| Item | Required | Description |
|------|----------|-------------|
| `.env` | ✓ | SMTP credentials — copy from `.env.example` and edit |
| `users.csv` | ✓ | Recipient list — copy from `users.csv.example` and replace with real data |
| Python packages | ✓ | Run `pip install -r requirements.txt` |
| Gmail app password | ✓* | Required when using Gmail (normal login password will not work) |
| `GITHUB_TOKEN` | — | Only if you enable AI rewriting — add to `.env` |

> `.env` and `users.csv` contain secrets and personal data. They are **not** in Git — create them locally on each machine.

Auto-generated on first run (no manual setup):

- `mail_templates.json` — saved email templates
- `sent_log.json` — log of sent addresses
- `daily_config.json` — daily auto-selection progress

### Setup from the repository

```bash
git clone https://github.com/sunny-days-365/Message-Sender.git
cd Message-Sender
pip install -r requirements.txt
copy .env.example .env
copy users.csv.example users.csv
```

Then fill in `.env` with your SMTP settings, update `users.csv` with your recipients, and start the app:

```bash
python main.py
```

### Setup

#### 1. Install dependencies

```bash
pip install -r requirements.txt
```

To build an EXE, also install PyInstaller:

```bash
pip install pyinstaller
```

#### 2. Email account settings (`.env`)

There is **no SMTP settings panel inside the app**. Mail account credentials are configured in a **`.env` file`** in the project folder (or next to the EXE when running the built app).

##### Using Gmail (recommended)

1. **Enable 2-Step Verification** on your Google Account  
   Go to [Google Account](https://myaccount.google.com/) → **Security** → turn on **2-Step Verification**

2. **Create an App Password**
   - On the same **Security** page, open **App passwords** (under 2-Step Verification)
   - Choose app: **Mail**, device: **Windows Computer** (or similar)
   - Copy the **16-character password** shown (your normal Gmail password will **not** work for SMTP)

3. **Create the `.env` file**

   In the project root (same folder as `main.py`), copy the bundled `.env.example` to `.env` and replace the placeholder values.

   ```bash
   copy .env.example .env
   ```

   Example `.env` contents:

   ```env
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=your-email@gmail.com
   SMTP_PASS=xxxx xxxx xxxx xxxx
   FROM_NAME=Alexandra
   ```

   | Variable | Required | Description |
   |----------|----------|-------------|
   | `SMTP_HOST` | — | SMTP server (Gmail: `smtp.gmail.com`) |
   | `SMTP_PORT` | — | SMTP port (Gmail: `587`) |
   | `SMTP_USER` | ✓ | Sender Gmail address |
   | `SMTP_PASS` | ✓ | App password from step 2 |
   | `FROM_NAME` | — | Display name shown to recipients |

4. **Verify**
   - Launch the app and send one test email to yourself
   - If it fails, check `.env` spelling, 2-Step Verification, and recreate the app password

##### Other email providers

| Provider | `SMTP_HOST` | `SMTP_PORT` |
|----------|-------------|-------------|
| Gmail | `smtp.gmail.com` | `587` |
| Outlook / Hotmail | `smtp-mail.outlook.com` | `587` |
| Yahoo! Mail (Japan) | `smtp.mail.yahoo.co.jp` | `587` |

Most providers require an app-specific password or enabling SMTP access. See your provider's documentation.

##### AI rewriting (optional)

To rewrite subject/body per send with GitHub Copilot API, add to `.env`:

```env
GITHUB_TOKEN=your-github-token
```

| Variable | Required | Description |
|----------|----------|-------------|
| `GITHUB_TOKEN` | — | Token from [GitHub Settings → Developer settings → Personal access tokens](https://github.com/settings/tokens) |

> **Warning:** `.env` contains secrets. Do not commit it to version control.

#### 3. Recipient list (`users.csv`)

`users.csv` is not included in the repository. Copy the sample file first:

```bash
copy users.csv.example users.csv
```

Then overwrite it with your real recipient data or place an exported CSV in the project folder.

| Column | Description |
|--------|-------------|
| `id` | User ID |
| `last_name` | Family name |
| `first_name` | Given name |
| `email` | Email address |
| `deleted_at` | If set, the row is skipped |

The display name is `last_name` + `first_name`. If empty, the email address is used as the name.

### Running the app

**From Python:**

```bash
python main.py
```

In VS Code, you can also use the task **「メール送信ツール 起動」**.

**From EXE:** Run `dist/MessageSender.exe`. Place `.env` in the same folder as the EXE.

### Building the EXE

```bash
pyinstaller build_exe.spec
```

For distribution, include `.env` and `users.csv` next to the EXE. `mail_templates.json`, `sent_log.json`, and `daily_config.json` are created on first run.

### Usage

#### Configuring the "Mail content" panel

Use the **「メール内容」 (Mail content)** section in the main window to set what gets sent.

| UI element | Description |
|------------|-------------|
| **Template** (dropdown) | Loads saved subject and body when selected |
| **💾 Save** | Save current subject/body as a new named template |
| **✏️ Overwrite** | Update the selected template with current subject/body |
| **🗑 Delete** | Remove the selected template |
| **Subject** | Email subject line |
| **Body** | Email body; `{name}` is replaced with each recipient's name |
| **🤖 AI rewrite** (checkbox) | When enabled, rephrases subject/body per recipient via GitHub Copilot API before sending |

**Typical workflow:**

1. Pick a template or type subject and body directly
2. Use `{name}` in the body for personalization (e.g. `{name}様`)
3. Click **Save** if you want to reuse the content later
4. Select recipients and click **送信開始 (Start sending)**

#### Basic send flow

1. Select users on the left, click **追加 ▶ (Add)** to move them to the send list
2. Configure subject and body in the Mail content panel
3. Click **送信開始 (Start sending)** and confirm

#### Daily auto-selection

1. **開始番号 (Start index)** — 1-based row number in the CSV
2. **件数 (Count)** — How many recipients per day
3. **今日の宛先を選択 (Select today's recipients)** — Fills the send list, skipping sent addresses

A fixed recipient is always added first. Progress is saved in `daily_config.json`.

#### Scheduled sending

Enable **送信間隔（ランダム） (Random interval)** and set min/max minutes between emails. Use **中止 (Cancel)** to stop. Minimizing sends the window to the system tray; sending continues.

### Project layout

```
Message-Sender/
├── main.py              # Application entry point
├── requirements.txt     # Python dependencies
├── build_exe.spec       # PyInstaller spec
├── README.md
├── .env.example         # Sample SMTP config (copy to `.env`)
├── users.csv.example    # Sample recipient CSV (copy to `users.csv`)
├── .env                 # SMTP / API credentials (create locally · not in Git)
├── users.csv            # Recipient list (create locally · not in Git)
├── mail_templates.json  # Saved templates (auto-generated)
├── sent_log.json        # Sent-address log (auto-generated)
└── daily_config.json    # Daily-send progress (auto-generated)
```

### Tech stack

- **GUI:** Tkinter
- **Email:** smtplib (multipart/alternative, Japanese header encoding)
- **Tray:** pystray + Pillow
- **Config:** python-dotenv
- **AI:** OpenAI SDK (via GitHub Models API)
- **Packaging:** PyInstaller

### Notes

- Bulk or unsolicited email may violate provider terms and local laws. Only email recipients who have opted in, and use reasonable send rates.
- Gmail requires an **app password**, not your regular login password.
- `users.csv` may contain personal data; handle and store it securely.
