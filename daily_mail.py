#!/usr/bin/env python3
"""
Günün Dersi — Mail Gönderici
─────────────────────────────────────────────────────
Her gün uygulamadaki kelimelerden deterministik olarak
10 kelime seçer ve HTML mailini Gmail üzerinden atar.

Uygulamadaki seçim algoritmasının BİREBİR AYNISI burada
da çalışır → kullanıcının tıkladığı link, mailde görülen
aynı 10 kelimeyi açar.

Gerekli ortam değişkenleri (GitHub Secrets'tan gelecek):
  GMAIL_USER       — gönderen Gmail adresi
  GMAIL_APP_PASS   — Gmail App Password (16 karakter)
  TO_EMAIL         — alıcı (kendi adresin)
  APP_URL          — uygulamanın yayımlandığı URL
                     (örn. https://kullaniciadi.github.io/repo/)
"""
import os
import re
import json
import smtplib
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path


# ─────────────────────────────────────────────────────
# 1. index.html dosyasından kelimeleri çek
# ─────────────────────────────────────────────────────
def extract_words(html_path: Path) -> list[dict]:
    """index.html içindeki INIT_WORDS dizisini ayıklar."""
    text = html_path.read_text(encoding="utf-8")
    pattern = re.compile(
        r'\{id:(\d+),en:"([^"]+)",tr:"([^"]+)",syn:"([^"]*)",usage:"([^"]*)",examples:\[(.*?)\],category:"([^"]+)"',
        re.DOTALL,
    )
    words = []
    for m in pattern.finditer(text):
        wid, en, tr, syn, usage, examples_raw, cat = m.groups()
        # examples ham hâlde: "ex1","ex2","ex3"
        examples = re.findall(r'"((?:[^"\\]|\\.)*)"', examples_raw)
        words.append({
            "id": int(wid),
            "en": en,
            "tr": tr,
            "syn": syn,
            "usage": usage,
            "examples": examples,
            "category": cat,
        })
    return words


# ─────────────────────────────────────────────────────
# 2. Deterministik 10 kelime seçimi (uygulamadakinin AYNISI)
# ─────────────────────────────────────────────────────
def daily_words(words: list[dict], date_str: str) -> list[dict]:
    seed = 0
    for ch in date_str:
        seed = (seed * 31 + ord(ch)) & 0xFFFFFFFF
    arr = list(words)
    s = seed
    for i in range(len(arr) - 1, 0, -1):
        s = (s * 1664525 + 1013904223) & 0xFFFFFFFF
        j = s % (i + 1)
        arr[i], arr[j] = arr[j], arr[i]
    return arr[:10]


# ─────────────────────────────────────────────────────
# 3. HTML mail içeriği
# ─────────────────────────────────────────────────────
def build_html(words: list[dict], date_str: str, app_url: str) -> str:
    rows = []
    for i, w in enumerate(words, 1):
        first_tr = w["tr"].split(",")[0].strip()
        ex = w["examples"][0] if w["examples"] else ""
        rows.append(f"""
        <tr>
          <td style="padding:12px 0;border-bottom:1px solid #eee;">
            <span style="display:inline-block;width:24px;color:#94a3b8;font-size:13px;">{i}.</span>
            <strong style="color:#1e293b;font-size:16px;">{w['en']}</strong>
            <span style="color:#a78bfa;margin-left:8px;font-size:14px;">— {first_tr}</span>
            <div style="margin-left:24px;margin-top:4px;color:#64748b;font-size:13px;font-style:italic;">{ex}</div>
          </td>
        </tr>""")

    link = f"{app_url.rstrip('/')}/?day={date_str}"

    return f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f8fafc;">
  <div style="max-width:600px;margin:0 auto;padding:24px;">
    <div style="background:white;border-radius:16px;padding:28px;box-shadow:0 2px 8px rgba(0,0,0,.05);">
      <h1 style="color:#6366f1;font-size:24px;margin:0 0 4px;">📅 Günün Dersi</h1>
      <p style="color:#94a3b8;font-size:14px;margin:0 0 24px;">{date_str} · Bugün için 10 kelime hazır</p>

      <a href="{link}" style="display:block;background:linear-gradient(135deg,#6366f1,#a78bfa);color:white;text-decoration:none;text-align:center;padding:14px;border-radius:12px;font-weight:700;margin-bottom:24px;">
        🎯 Çalışmaya Başla →
      </a>

      <h2 style="color:#1e293b;font-size:16px;margin:0 0 8px;">Bugünün Kelimeleri</h2>
      <table style="width:100%;border-collapse:collapse;">
        {"".join(rows)}
      </table>

      <p style="color:#94a3b8;font-size:12px;margin-top:24px;text-align:center;">
        Linke tıklayınca uygulama bu 10 kelimeyle açılır:<br>
        Flashcard → Quiz → Telaffuz, hepsi bir arada.
      </p>
    </div>
  </div>
</body>
</html>"""


# ─────────────────────────────────────────────────────
# 4. Mail gönder
# ─────────────────────────────────────────────────────
def send_mail(html: str, date_str: str):
    user = os.environ["GMAIL_USER"]
    app_pass = os.environ["GMAIL_APP_PASS"]
    to_email = os.environ["TO_EMAIL"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📅 Günün Dersi — {date_str}"
    msg["From"] = user
    msg["To"] = to_email
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(user, app_pass)
        server.send_message(msg)


# ─────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────
def main():
    html_path = Path(__file__).parent / "index.html"
    words = extract_words(html_path)
    print(f"✓ {len(words)} kelime yüklendi")

    # Türkiye saati
    tz = datetime.timezone(datetime.timedelta(hours=3))
    today = datetime.datetime.now(tz).strftime("%Y-%m-%d")

    selected = daily_words(words, today)
    print(f"✓ {today} için 10 kelime seçildi:")
    for w in selected:
        print(f"   • {w['en']} — {w['tr'].split(',')[0]}")

    app_url = os.environ.get("APP_URL", "https://example.github.io/repo")
    html = build_html(selected, today, app_url)

    # Test modu: TO_EMAIL yoksa sadece konsola yaz
    if "GMAIL_USER" not in os.environ:
        print("\n⚠️  GMAIL_USER yok — mail gönderilmiyor (test modu)")
        print(f"Link: {app_url}/?day={today}")
        return

    send_mail(html, today)
    print(f"✓ Mail gönderildi → {os.environ['TO_EMAIL']}")


if __name__ == "__main__":
    main()
