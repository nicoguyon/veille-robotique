#!/usr/bin/env python3
"""Veille robotique — programme les posts X (via Late) pour les news featured.

Lit data/latest.json : chaque item `featured` avec un champ `x_post` (texte rédigé
par l'agent, ≤ 230 caractères, SANS lien) donne un post X programmé sur le compte
@nico16184, avec le lien vers la newsletter ajouté automatiquement.
Les posts sont étalés : +20 min, +22 h, +46 h après le run.

Usage : python3 scripts/post_x.py [--dry-run]
Requiert : LATE_API_KEY (env ou ~/.brand_factory/keys.env)
"""
import argparse
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE_URL = "https://veille-robotique.comptoiria.com"
X_ACCOUNT_ID = "69a8b75bdc8cab9432b8bf60"  # @nico16184 sur Late
OFFSETS_H = [2, 22, 46]  # étalement (heures après le run) — 2 h de fenêtre opt-out avant le 1er
CTA = f"\n\nLa veille robotique de la semaine 👉 {PAGE_URL}"


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


def late_api(path, key, payload=None):
    req = urllib.request.Request(f"https://getlate.dev/api/v1{path}",
                                 data=json.dumps(payload).encode() if payload else None,
                                 method="POST" if payload else "GET",
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json",
                                          "User-Agent": "curl/8.7.1"})
    for attempt in range(3):  # Late renvoie parfois un 500 transitoire → retry
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code >= 500 and attempt < 2:
                time.sleep(5)
                continue
            sys.exit(f"Late {e.code}: {e.read().decode()[:300]}")


def build_content(item):
    text = (item.get("x_post") or "").strip()
    if not text:  # fallback si l'agent n'a pas rédigé de x_post
        text = item.get("title", "").strip()
    if len(text) > 240:
        text = text[:237].rsplit(" ", 1)[0] + "…"
    return text + CTA


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--viral-only", action="store_true",
                    help="ne crée que le draft viral (pas les posts news programmés)")
    args = ap.parse_args()

    key = load_key("LATE_API_KEY")
    if not key:
        sys.exit("LATE_API_KEY introuvable")

    data = json.loads((ROOT / "data" / "latest.json").read_text())
    featured = [i for c in data.get("categories", []) for i in c.get("items", [])
                if i.get("featured")][:len(OFFSETS_H)]
    if not featured:
        print("Aucune news featured — pas de post X.")
        return

    now = datetime.now(timezone.utc)
    scheduled = []
    for item, off in zip([] if args.viral_only else featured, OFFSETS_H):
        content = build_content(item)
        when = (now + timedelta(hours=off)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        if args.dry_run:
            print(f"--- {when}\n{content}\n")
            continue
        resp = late_api("/posts", key, {
            "content": content,
            "scheduledFor": when,
            "platforms": [{"platform": "twitter", "accountId": X_ACCOUNT_ID}],
        })
        post = resp.get("post") or resp
        print(f"✓ Post programmé {when} → id {post.get('_id') or post.get('id')} "
              f"(status {post.get('status')})")
        scheduled.append({"content": content, "scheduled_utc": when,
                          "late_id": post.get("_id") or post.get("id")})

    # Post viral hebdo : créé en DRAFT Late (opt-in — Nico valide/corrige sur getlate.dev)
    viral = (data.get("x_viral") or "").strip()
    if viral:
        content = viral if PAGE_URL in viral else viral + f"\n{PAGE_URL}"
        if args.dry_run:
            print(f"--- DRAFT viral (à valider)\n{content}\n")
        else:
            resp = late_api("/posts", key, {
                "content": content,
                "platforms": [{"platform": "twitter", "accountId": X_ACCOUNT_ID}],
            })  # sans scheduledFor → reste en draft tant que Nico ne l'a pas validé
            post = resp.get("post") or resp
            print(f"✓ Post viral créé en DRAFT Late → id {post.get('_id') or post.get('id')} "
                  f"(status {post.get('status')})")
            scheduled.append({"content": content, "scheduled_utc": None,
                              "late_id": post.get("_id") or post.get("id"), "draft": True})

    if not args.dry_run and scheduled:
        # consommé par send_email.py pour la section « tweets proposés » (opt-out)
        (ROOT / "data" / "x_posts_scheduled.json").write_text(
            json.dumps({"date": now.strftime("%Y-%m-%d"), "posts": scheduled},
                       ensure_ascii=False, indent=1))

    if not args.dry_run:
        posts = late_api(f"/posts?limit={len(featured)}", key)
        lst = posts.get("posts") or posts.get("data") or []
        bad = [p for p in lst if p.get("status") not in ("scheduled", "published")]
        if bad:
            print(f"⚠ {len(bad)} post(s) pas en scheduled/published — vérifier sur getlate.dev")
        else:
            print(f"✓ {len(lst)} posts confirmés côté Late")


if __name__ == "__main__":
    main()
