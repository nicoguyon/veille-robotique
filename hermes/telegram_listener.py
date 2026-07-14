#!/usr/bin/env python3
"""Démon Telegram de validation (VPS Hermes) — écoute les clics de Nico.

Callbacks gérés :
  cancel:<late_id>  → supprime le post Late (draft ou programmé non publié)
  publish:<late_id> → publie le draft immédiatement.
    ⚠ L'API Late ne sait pas « publier un draft » : il faut le SUPPRIMER puis le
    recréer avec un scheduledFor 5 minutes dans le passé (= publication immédiate).

Tourne en long-polling (getUpdates). Lancé par systemd : veille-telegram.service.
Requiert : TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, LATE_API_KEY (env ou keys.env).
"""
import json
import os
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

X_ACCOUNT_ID = "69a8b75bdc8cab9432b8bf60"  # @nico16184 sur Late


def load_key(name):
    v = os.environ.get(name)
    if v:
        return v
    for p in (Path.home() / ".brand_factory" / "keys.env",
              Path("/root/.brand_factory/keys.env")):
        if p.exists():
            for line in p.read_text().splitlines():
                if line.startswith(f"{name}="):
                    return line.split("=", 1)[1].strip().strip('"')
    return None


TOKEN = load_key("TELEGRAM_BOT_TOKEN")
CHAT = str(load_key("TELEGRAM_CHAT_ID") or "")
LATE = load_key("LATE_API_KEY")


def tg(method, payload):
    req = urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/{method}",
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=70) as r:
        return json.load(r)


def late(path, payload=None, method=None):
    req = urllib.request.Request(f"https://getlate.dev/api/v1{path}",
                                 data=json.dumps(payload).encode() if payload else None,
                                 method=method or ("POST" if payload else "GET"),
                                 headers={"Authorization": f"Bearer {LATE}",
                                          "Content-Type": "application/json",
                                          "User-Agent": "curl/8.7.1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r) if r.status != 204 else {}


def handle(action, lid):
    if action == "cancel":
        late(f"/posts/{lid}", method="DELETE")
        return "❌ Annulé — ce post ne partira pas."
    if action == "publish":
        post = late(f"/posts/{lid}")
        post = post.get("post") or post
        content = post.get("content")
        if not content:
            return "⚠ Post introuvable sur Late (déjà traité ?)."
        late(f"/posts/{lid}", method="DELETE")
        past = (datetime.now(timezone.utc) - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        late("/posts", {"content": content, "scheduledFor": past,
                        "platforms": [{"platform": "twitter", "accountId": X_ACCOUNT_ID}]})
        return "✅ Publié sur @nico16184 !"
    return "⚠ Action inconnue."


def main():
    global TOKEN, CHAT, LATE
    while not (TOKEN and LATE):
        print("TELEGRAM_BOT_TOKEN ou LATE_API_KEY manquant — nouvelle tentative dans 5 min "
              "(la sync des clés tourne toutes les 15 min).")
        time.sleep(300)
        TOKEN, CHAT, LATE = (load_key("TELEGRAM_BOT_TOKEN"),
                             str(load_key("TELEGRAM_CHAT_ID") or ""), load_key("LATE_API_KEY"))
    offset = 0
    print("Listener Telegram démarré.")
    while True:
        try:
            updates = tg("getUpdates", {"offset": offset, "timeout": 50,
                                        "allowed_updates": ["callback_query", "message"]})
        except Exception as e:
            print("getUpdates KO:", e)
            time.sleep(10)
            continue
        for u in updates.get("result", []):
            offset = u["update_id"] + 1
            cq = u.get("callback_query")
            if not cq:
                continue
            if CHAT and str(cq.get("message", {}).get("chat", {}).get("id")) != CHAT:
                continue  # on n'obéit qu'à Nico
            data = cq.get("data", "")
            action, _, lid = data.partition(":")
            try:
                result = handle(action, lid)
            except Exception as e:
                result = f"⚠ Erreur : {str(e)[:120]}"
            try:
                tg("answerCallbackQuery", {"callback_query_id": cq["id"], "text": result[:190]})
                msg = cq.get("message", {})
                tg("editMessageText", {
                    "chat_id": msg["chat"]["id"], "message_id": msg["message_id"],
                    "text": (msg.get("text") or "") + f"\n\n{result}",
                })
            except Exception as e:
                print("réponse TG KO:", e)


if __name__ == "__main__":
    main()
