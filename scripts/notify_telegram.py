#!/usr/bin/env python3
"""Veille robotique — notification Telegram de fin de pipeline, avec validation.

Envoie à Nico : le récap de l'édition + chaque tweet programmé (bouton ❌ Annuler)
+ le post viral en draft (boutons ✅ Publier / 🗑 Jeter). Les clics sont traités
par hermes/telegram_listener.py (démon sur le VPS Hermes).

Usage : python3 scripts/notify_telegram.py
Requiert : TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID (env ou keys.env).
Sans token : warning et sortie 0 (le pipeline continue).
"""
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE_URL = "https://veille-robotique.comptoiria.com"


def load_key(name):
    v = os.environ.get(name)
    if v:
        return v
    keys = Path.home() / ".brand_factory" / "keys.env"
    if keys.exists():
        for line in keys.read_text().splitlines():
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip().strip('"')
    return None


def tg(method, token, payload):
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/{method}",
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main():
    token, chat = load_key("TELEGRAM_BOT_TOKEN"), load_key("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("⚠ TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID absents — notification Telegram sautée.")
        return

    data = json.loads((ROOT / "data" / "latest.json").read_text())
    title = data.get("newsletter_title") or data.get("week_label", "")

    # 1. Message récap
    tg("sendMessage", token, {
        "chat_id": chat, "parse_mode": "HTML", "disable_web_page_preview": False,
        "text": (f"🤖 <b>{title}</b>\n"
                 f"{data.get('newsletter_subtitle', '')}\n\n"
                 f"📄 {PAGE_URL}\n"
                 f"✉️ Brouillon Substack prêt à relire"),
    })

    # 2. Tweets programmés + draft viral, avec boutons de validation
    sched = ROOT / "data" / "x_posts_scheduled.json"
    if not sched.exists():
        return
    posts = json.loads(sched.read_text()).get("posts", [])
    for p in posts:
        lid = p.get("late_id")
        if not lid:
            continue
        if p.get("draft"):
            text = f"🔥 <b>POST VIRAL — à valider</b>\n\n{p['content']}"
            kb = [[{"text": "✅ Publier maintenant", "callback_data": f"publish:{lid}"},
                   {"text": "🗑 Jeter", "callback_data": f"cancel:{lid}"}]]
        else:
            when = (p.get("scheduled_utc") or "")[:16].replace("T", " ")
            text = f"🐦 <b>Tweet programmé</b> (départ {when} UTC)\n\n{p['content']}"
            kb = [[{"text": "❌ Annuler ce tweet", "callback_data": f"cancel:{lid}"}]]
        tg("sendMessage", token, {
            "chat_id": chat, "parse_mode": "HTML", "disable_web_page_preview": True,
            "text": text, "reply_markup": {"inline_keyboard": kb},
        })
    print(f"✓ Notification Telegram envoyée ({len(posts)} posts avec boutons)")


if __name__ == "__main__":
    main()
