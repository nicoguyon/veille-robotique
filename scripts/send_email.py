#!/usr/bin/env python3
"""Veille robotique — envoie l'email récap hebdo via Resend.

Lit data/latest.json, envoie le top des news + lien vers la page.
Usage : python3 scripts/send_email.py
Requiert : RESEND_API_KEY (env ou ~/.brand_factory/keys.env)
"""
import html
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE_URL = "https://veille-robotique.comptoiria.com"
TO = "nicoguyon@gmail.com"


def load_key(name, default=None):
    v = os.environ.get(name)
    if v:
        return v
    keys = Path.home() / ".brand_factory" / "keys.env"
    if keys.exists():
        for line in keys.read_text().splitlines():
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip().strip('"')
    return default


def esc(s):
    return html.escape(s or "")


def fmt_n(n):
    try:
        n = int(n)
    except (TypeError, ValueError):
        return ""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}k"
    return str(n)


def news_block(item):
    met = item.get("metrics") or {}
    likes = fmt_n(met.get("likes"))
    stats = f" · ❤️ {likes}" if likes else ""
    company = f'<span style="display:inline-block;background:#16130F;color:#fff;font-size:11px;font-weight:600;padding:2px 9px;border-radius:99px;margin-bottom:6px">{esc(item.get("company"))}</span><br>' if item.get("company") else ""
    return f'''<tr><td style="padding:14px 0;border-bottom:1px solid #EBE7DF">
      {company}
      <div style="font-size:16px;font-weight:600;color:#16130F;line-height:1.35">{esc(item.get("title"))}</div>
      <div style="font-size:14px;color:#55504A;line-height:1.5;padding-top:4px">{esc(item.get("summary"))}</div>
      <div style="font-size:12px;color:#8A847B;padding-top:6px">
        <a href="{esc(item.get("url"))}" style="color:#FF4D00;text-decoration:none;font-weight:600">Voir sur X →</a>{stats}
      </div>
    </td></tr>'''


def tweets_block():
    """Section « tweets programmés » (opt-out) si post_x.py a tourné aujourd'hui."""
    f = ROOT / "data" / "x_posts_scheduled.json"
    if not f.exists():
        return ""
    from datetime import datetime, timezone
    d = json.loads(f.read_text())
    if d.get("date") != datetime.now(timezone.utc).strftime("%Y-%m-%d"):
        return ""
    try:
        from zoneinfo import ZoneInfo
        paris = ZoneInfo("Europe/Paris")
    except Exception:
        paris = None
    rows = ""
    for p in d.get("posts", []):
        if p.get("draft"):
            label = "🔥 POST VIRAL — en draft, à valider ou corriger sur getlate.dev"
            rows += f'''<tr><td style="padding:10px 0;border-bottom:1px solid #EBE7DF">
          <div style="font-size:11px;font-weight:700;color:#16130F;text-transform:uppercase;letter-spacing:1px">{esc(label)}</div>
          <div style="font-size:13px;color:#3E3931;line-height:1.5;padding-top:4px;white-space:pre-wrap">{esc(p["content"])}</div>
        </td></tr>'''
            continue
        when = p["scheduled_utc"]
        try:
            dt = datetime.strptime(when, "%Y-%m-%dT%H:%M:%S.000Z").replace(tzinfo=timezone.utc)
            label = dt.astimezone(paris).strftime("%a %d/%m %H:%M") if paris else when
        except ValueError:
            label = when
        rows += f'''<tr><td style="padding:10px 0;border-bottom:1px solid #EBE7DF">
          <div style="font-size:11px;font-weight:700;color:#FF4D00;text-transform:uppercase;letter-spacing:1px">Départ : {esc(label)} (Paris)</div>
          <div style="font-size:13px;color:#3E3931;line-height:1.5;padding-top:4px;white-space:pre-wrap">{esc(p["content"])}</div>
        </td></tr>'''
    return f'''<tr><td style="padding:6px 32px 8px">
      <div style="font-size:17px;font-weight:700;color:#16130F;padding:14px 0 2px">🐦 Tweets programmés sur @nico16184</div>
      <div style="font-size:12px;color:#8A847B">Ils partiront automatiquement — pour modifier ou annuler :
        <a href="https://getlate.dev" style="color:#FF4D00;font-weight:600">getlate.dev</a></div>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows}</table>
    </td></tr>'''


def main():
    key = load_key("RESEND_API_KEY")
    if not key:
        sys.exit("RESEND_API_KEY introuvable")
    sender = "veille-robotique@comptoiria.com"  # domaine vérifié Resend

    data = json.loads((ROOT / "data" / "latest.json").read_text())
    items = [i for c in data.get("categories", []) for i in c.get("items", [])]
    top = [i for i in items if i.get("featured")] + [i for i in items if not i.get("featured")]
    top = top[:6]

    body = f'''<!DOCTYPE html><html><body style="margin:0;padding:0;background:#FAF9F6;font-family:-apple-system,'Segoe UI',Helvetica,Arial,sans-serif">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#FAF9F6;padding:28px 12px"><tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#fff;border-radius:18px;overflow:hidden;border:1px solid #EBE7DF">
  <tr><td style="background:#16130F;padding:30px 32px">
    <div style="color:#FF4D00;font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase">Veille hebdo · Robotique × X</div>
    <div style="color:#fff;font-size:26px;font-weight:700;padding-top:6px">🤖 Veille Robotique</div>
    <div style="color:#B8B2A8;font-size:14px;padding-top:4px">{esc(data.get("week_label"))}</div>
  </td></tr>
  <tr><td style="padding:26px 32px 8px">
    <div style="font-size:15px;color:#3E3931;line-height:1.55">{esc(data.get("edito"))}</div>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding-top:10px">{"".join(news_block(i) for i in top)}</table>
  </td></tr>
  {tweets_block()}
  <tr><td align="center" style="padding:26px 32px 30px">
    <a href="{PAGE_URL}" style="display:inline-block;background:#FF4D00;color:#fff;font-size:15px;font-weight:700;text-decoration:none;padding:13px 30px;border-radius:99px">Voir la veille complète →</a>
    <div style="font-size:12px;color:#8A847B;padding-top:14px">Toutes les news par catégorie, avec les démos vidéo de la semaine</div>
  </td></tr>
</table>
<div style="font-size:11px;color:#B8B2A8;padding-top:16px">Agent de veille automatique · Comptoir IA</div>
</td></tr></table></body></html>'''

    payload = {
        "from": f"Veille Robotique <{sender}>",
        "to": [TO],
        "subject": f"🤖 Veille Robotique — {data.get('week_label')}",
        "html": body,
    }
    req = urllib.request.Request("https://api.resend.com/emails",
                                 data=json.dumps(payload).encode(),
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json",
                                          "User-Agent": "curl/8.7.1"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            print("✓ Email envoyé :", json.load(r).get("id"))
    except urllib.error.HTTPError as e:
        sys.exit(f"Resend {e.code}: {e.read().decode()[:500]}")


if __name__ == "__main__":
    main()
