#!/usr/bin/env python3
"""Veille robotique — archive les news de l'édition dans Supabase.

Table : public.robotics_news (projet x-likes-gallery, vnljuhngzbovgynczxyy).
Upsert par URL de tweet (les doublons inter-éditions sont ignorés).

Usage : python3 scripts/store_news.py
Requiert : SUPABASE_VEILLE_URL + SUPABASE_VEILLE_SERVICE_KEY (env ou keys.env).
Sans clé : warning et sortie 0 (le pipeline continue).
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


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


def main():
    url = load_key("SUPABASE_VEILLE_URL") or "https://vnljuhngzbovgynczxyy.supabase.co"
    key = load_key("SUPABASE_VEILLE_SERVICE_KEY")
    if not key:
        print("⚠ SUPABASE_VEILLE_SERVICE_KEY absente — archivage Supabase sauté.")
        return

    data = json.loads((ROOT / "data" / "latest.json").read_text())
    rows = []
    for c in data.get("categories", []):
        for it in c.get("items", []):
            m = it.get("media") or {}
            met = it.get("metrics") or {}
            rows.append({
                "edition_date": data["date"],
                "week_label": data.get("week_label"),
                "category_id": c["id"],
                "category_title": c.get("title"),
                "title": it["title"],
                "summary": it.get("summary"),
                "company": it.get("company"),
                "tag": it.get("tag"),
                "featured": bool(it.get("featured")),
                "news_date": it.get("date"),
                "url": it["url"],
                "author_handle": it.get("author_handle"),
                "likes": (met.get("likes") or None),
                "views": (met.get("views") or None),
                "media_type": m.get("type"),
                "media_image": m.get("image"),
                "media_video": m.get("video"),
                "x_post": it.get("x_post"),
            })

    req = urllib.request.Request(
        f"{url}/rest/v1/robotics_news?on_conflict=url",
        data=json.dumps(rows).encode(),
        headers={"apikey": key, "Authorization": f"Bearer {key}",
                 "Content-Type": "application/json",
                 "Prefer": "resolution=ignore-duplicates",
                 "User-Agent": "curl/8.7.1"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            print(f"✓ {len(rows)} news archivées dans Supabase (HTTP {r.status})")
    except urllib.error.HTTPError as e:
        sys.exit(f"Supabase {e.code}: {e.read().decode()[:300]}")


if __name__ == "__main__":
    main()
