from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
import os
import secrets
import string
import re
import imaplib
import email
from email.header import decode_header
from functools import wraps
from datetime import datetime, timedelta
import ssl

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# ==================== AYARLAR ====================
# Admin şifresini mutlaka değiştir!
ADMIN_PASSWORD = "Kyrasstore102"

# Gmail IMAP
IMAP_SERVER = "imap.gmail.com"
IMAP_PORT = 993

# Kod ararken son kaç dakikalık maillere bakılsın
CODE_SEARCH_MINUTES = 30

DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            email TEXT NOT NULL,
            password TEXT NOT NULL,
            current_code TEXT DEFAULT '',
            note TEXT DEFAULT '',
            created_at TEXT,
            updated_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated


def generate_code(length=8):
    chars = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))


def decode_mime_header(value):
    if not value:
        return ""
    parts = decode_header(value)
    result = []
    for part, enc in parts:
        if isinstance(part, bytes):
            try:
                result.append(part.decode(enc or "utf-8", errors="ignore"))
            except Exception:
                result.append(part.decode("utf-8", errors="ignore"))
        else:
            result.append(part)
    return " ".join(result)


def extract_code_from_text(text):
    """Mail içeriğinden doğrulama kodu çıkarmaya çalışır."""
    if not text:
        return None

    # Önce en yaygın kalıpları dene
    patterns = [
        r"(?:code|kod|verification|doğrulama|otp|pin)[\s:]*[is]*[\s:]*(\d{4,8})",
        r"(?:your code is|kodunuz|doğrulama kodu)[\s:]*(\d{4,8})",
        r"\b(\d{6})\b",          # 6 haneli kod (en yaygın)
        r"\b(\d{4})\b",          # 4 haneli
        r"\b(\d{8})\b",          # 8 haneli
    ]

    text_lower = text.lower()
    for pattern in patterns:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            return match.group(1)

    return None


def fetch_latest_code_from_gmail(email_addr, password):
    """
    Gmail'e bağlanır, son mailleri tarar ve doğrulama kodu bulmaya çalışır.
    Başarılıysa (kod, None) döner, hata varsa (None, hata_mesajı) döner.
    """
    try:
        context = ssl.create_default_context()
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT, ssl_context=context)
        mail.login(email_addr, password)
        mail.select("INBOX")

        # Son X dakikadaki mailleri al
        since_date = (datetime.utcnow() - timedelta(minutes=CODE_SEARCH_MINUTES)).strftime("%d-%b-%Y")
        status, messages = mail.search(None, f'(SINCE "{since_date}")')

        if status != "OK" or not messages[0]:
            # Hiç mail yoksa tüm son 20 maili dene
            status, messages = mail.search(None, "ALL")
            if status != "OK" or not messages[0]:
                mail.logout()
                return None, "Mail kutusunda hiç mesaj yok"

        mail_ids = messages[0].split()
        # En yeniden eskiye doğru bak (son 15 mail yeterli)
        mail_ids = mail_ids[-15:][::-1]

        found_code = None
        for mid in mail_ids:
            status, msg_data = mail.fetch(mid, "(RFC822)")
            if status != "OK":
                continue

            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            subject = decode_mime_header(msg.get("Subject", ""))
            from_ = decode_mime_header(msg.get("From", ""))

            # Body'yi çıkar
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    ctype = part.get_content_type()
                    if ctype in ("text/plain", "text/html"):
                        try:
                            payload = part.get_payload(decode=True)
                            if payload:
                                charset = part.get_content_charset() or "utf-8"
                                body += payload.decode(charset, errors="ignore") + "\n"
                        except Exception:
                            pass
            else:
                try:
                    payload = msg.get_payload(decode=True)
                    if payload:
                        charset = msg.get_content_charset() or "utf-8"
                        body = payload.decode(charset, errors="ignore")
                except Exception:
                    body = str(msg.get_payload())

            # Konu + body içinde kod ara
            full_text = subject + "\n" + body + "\n" + from_
            code = extract_code_from_text(full_text)
            if code:
                found_code = code
                break  # En yeni bulunanı al

        mail.logout()

        if found_code:
            return found_code, None
        return None, "Son maillerde doğrulama kodu bulunamadı. Biraz bekleyip tekrar deneyin."

    except imaplib.IMAP4.error as e:
        err = str(e).lower()
        if "authentication failed" in err or "invalid credentials" in err:
            return None, "Mail girişi başarısız. Şifre yanlış veya Gmail App Password gerekiyor."
        return None, f"IMAP hatası: {str(e)[:80]}"
    except Exception as e:
        return None, f"Bağlantı hatası: {str(e)[:80]}"


# ==================== ALICI SAYFALARI ====================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/check", methods=["POST"])
def check_code():
    code = request.form.get("code", "").strip().upper()
    if not code:
        return render_template("index.html", error="Kod giriniz.")

    conn = get_db()
    row = conn.execute("SELECT * FROM deliveries WHERE code = ?", (code,)).fetchone()
    conn.close()

    if not row:
        return render_template("index.html", error="Geçersiz kod. Lütfen kontrol edin.")

    return render_template(
        "delivery.html",
        delivery_code=row["code"],
        email=row["email"],
        password=row["password"],
        note=row["note"] or "",
    )


@app.route("/api/get_code/<delivery_code>")
def api_get_code(delivery_code):
    delivery_code = delivery_code.strip().upper()
    conn = get_db()
    row = conn.execute(
        "SELECT email, password, current_code FROM deliveries WHERE code = ?",
        (delivery_code,),
    ).fetchone()
    conn.close()

    if not row:
        return jsonify({"ok": False, "code": "", "message": "Teslimat bulunamadı"})

    # 1) Önce elle girilmiş kod varsa onu ver (manuel override)
    if row["current_code"] and row["current_code"].strip():
        return jsonify({
            "ok": True,
            "code": row["current_code"].strip(),
            "message": "Kod hazır (manuel)",
            "source": "manual"
        })

    # 2) Otomatik Gmail'den çek
    code, error = fetch_latest_code_from_gmail(row["email"], row["password"])

    if code:
        return jsonify({
            "ok": True,
            "code": code,
            "message": "Kod Gmail'den alındı ✓",
            "source": "gmail"
        })

    return jsonify({
        "ok": True,
        "code": "",
        "message": error or "Kod henüz gelmedi. Birkaç saniye sonra tekrar deneyin.",
        "source": "none"
    })


# ==================== ADMIN ====================

@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_logged_in"):
        return redirect(url_for("admin_panel"))

    error = None
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            return redirect(url_for("admin_panel"))
        error = "Yanlış şifre"

    return render_template("admin_login.html", error=error)


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/admin/panel")
@login_required
def admin_panel():
    conn = get_db()
    rows = conn.execute("SELECT * FROM deliveries ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("admin_panel.html", deliveries=rows)


@app.route("/admin/add", methods=["POST"])
@login_required
def admin_add():
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()
    note = request.form.get("note", "").strip()
    custom_code = request.form.get("custom_code", "").strip().upper()

    if not email or not password:
        return redirect(url_for("admin_panel"))

    code = custom_code if custom_code else generate_code()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO deliveries (code, email, password, note, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (code, email, password, note, now, now),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        code = generate_code()
        conn.execute(
            "INSERT INTO deliveries (code, email, password, note, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (code, email, password, note, now, now),
        )
        conn.commit()
    conn.close()
    return redirect(url_for("admin_panel"))


@app.route("/admin/update_code", methods=["POST"])
@login_required
def admin_update_code():
    """Manuel kod girişi (yedek)."""
    delivery_id = request.form.get("id")
    new_code = request.form.get("current_code", "").strip()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db()
    conn.execute(
        "UPDATE deliveries SET current_code = ?, updated_at = ? WHERE id = ?",
        (new_code, now, delivery_id),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("admin_panel"))


@app.route("/admin/delete/<int:delivery_id>", methods=["POST"])
@login_required
def admin_delete(delivery_id):
    conn = get_db()
    conn.execute("DELETE FROM deliveries WHERE id = ?", (delivery_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_panel"))


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
