#!/usr/bin/env python3
"""
Haftalık Quiz — Mail Gönderici
─────────────────────────────────────────────────────
Her Pazar 09:00'da çalışır.
Tüm kelime havuzundan deterministik olarak 30 kelime seçer,
linke tıklandığında 30 soruluk quiz başlatılır.

JS tarafındaki getWeeklyWords() ile birebir aynı sonucu üretir,
böylece mailde önizleme = quizdeki kelimeler.

Gerekli ortam değişkenleri (daily_mail.py ile aynı secrets):
  GMAIL_USER, GMAIL_APP_PASS, TO_EMAIL, APP_URL
"""
import os
import re
import smtplib
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path


def extract_words(html_path: Path) -> list[dict]:
    """index.html içindeki kelime listesini ayıklar (daily_mail.py ile aynı)."""
    text = html_path.read_text(encoding="utf-8")
    pattern = re.compile(
        r'\{id:(\d+),en:"([^"]+)",tr:"([^"]+)",syn:"([^"]*)",usage:"([^"]*)",examples:\[(.*?)\],category:"([^"]+)"',
        re.DOTALL,
    )
    words = []
    for m in pattern.finditer(text):
        wid, en, tr, syn, usage, examples_raw, cat = m.groups()
        examples = re.findall(r'"((?:[^"\\]|\\.)*)"', examples_raw)
        words.append({
            "id": int(wid), "en": en, "tr": tr, "syn": syn,
            "usage": usage, "examples": examples, "category": cat,
        })
    return words


def weekly_words(words: list[dict], date_str: str) -> list[dict]:
    """JS getWeeklyWords() ile bire bir aynı seçim."""
    seed = 0
    for ch in date_str:
        seed = (seed * 31 + ord(ch)) & 0xFFFFFFFF
    # Günlük seçimden farklı olsun diye XOR ile karıştır
    seed = (seed ^ 0xABCDEF) & 0xFFFFFFFF
    arr = list(words)
    s = seed
    for i in range(len(arr) - 1, 0, -1):
        s = (s * 1664525 + 1013904223) & 0xFFFFFFFF
        j = s % (i + 1)
        arr[i], arr[j] = arr[j], arr[i]
    return arr[:30]


def build_html(words: list[dict], date_str: str, app_url: str) -> str:
    # Önizleme: ilk 8 kelime mailde görünür, kalanı surpriz olsun
    preview_rows = []
    for i, w in enumerate(words[:8], 1):
        first_tr = w["tr"].split(",")[0].strip()
        preview_rows.append(f"""
        <tr>
          <td style="padding:8px 0;border-bottom:1px solid #eee;">
            <span style="color:#94a3b8;font-size:13px;width:24px;display:inline-block;">{i}.</span>
            <strong style="color:#1e293b;font-size:15px;">{w['en']}</strong>
            <span style="color:#a78bfa;margin-left:8px;font-size:13px;">— {first_tr}</span>
          </td>
        </tr>""")

    link = f"{app_url.rstrip('/')}/?weekly={date_str}"
    remaining = len(words) - 8

    return f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f8fafc;">
  <div style="max-width:600px;margin:0 auto;padding:24px;">
    <div style="background:white;border-radius:16px;padding:28px;box-shadow:0 2px 8px rgba(0,0,0,.05);">
      <h1 style="color:#10b981;font-size:24px;margin:0 0 4px;">📊 Haftalık Quiz</h1>
      <p style="color:#94a3b8;font-size:14px;margin:0 0 24px;">{date_str} · 30 soru · Bu haftanın sınavı</p>

      <a href="{link}" style="display:block;background:linear-gradient(135deg,#10b981,#34d399);color:white;text-decoration:none;text-align:center;padding:14px;border-radius:12px;font-weight:700;margin-bottom:24px;">
        🎯 Quiz'i Başlat →
      </a>

      <h2 style="color:#1e293b;font-size:16px;margin:0 0 8px;">Önizleme (ilk 8 kelime)</h2>
      <table style="width:100%;border-collapse:collapse;">
        {"".join(preview_rows)}
      </table>
      <p style="color:#64748b;font-size:13px;margin-top:14px;text-align:center;font-style:italic;">
        ...ve {remaining} kelime daha quiz içinde seni bekliyor 🎲
      </p>

      <p style="color:#94a3b8;font-size:12px;margin-top:20px;text-align:center;">
        Bu hafta öğrendiğin tüm kelimeleri test et.<br>
        Skor 25+ ise tebrikler — hedefin tutmuş demektir.
      </p>
    </div>
  </div>
</body>
</html>"""


def send_mail(html: str, date_str: str):
    user = os.environ["GMAIL_USER"]
    app_pass = os.environ["GMAIL_APP_PASS"]
    to_email = os.environ["TO_EMAIL"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📊 Haftalık Quiz — {date_str}"
    msg["From"] = user
    msg["To"] = to_email
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(user, app_pass)
        server.send_message(msg)


def main():
    html_path = Path(__file__).parent / "index.html"
    words = extract_words(html_path)
    print(f"✓ {len(words)} kelime yüklendi")

    tz = datetime.timezone(datetime.timedelta(hours=3))
    today = datetime.datetime.now(tz).strftime("%Y-%m-%d")

    selected = weekly_words(words, today)
    print(f"✓ {today} haftalık quizi için 30 kelime seçildi:")
    for w in selected[:5]:
        print(f"   • {w['en']} — {w['tr'].split(',')[0]}")
    print(f"   ...ve {len(selected) - 5} kelime daha")

    app_url = os.environ.get("APP_URL", "https://example.github.io/repo")
    html = build_html(selected, today, app_url)

    if "GMAIL_USER" not in os.environ:
        print("\n⚠️  GMAIL_USER yok — mail gönderilmiyor (test modu)")
        print(f"Link: {app_url}/?weekly={today}")
        return

    send_mail(html, today)
    print(f"✓ Mail gönderildi → {os.environ['TO_EMAIL']}")


if __name__ == "__main__":
    main()
