#!/usr/bin/env python3
"""Veille robotique — crée le post hebdo en BROUILLON sur le Substack Comptoir IA.

API interne Substack (pas d'API officielle) : auth par cookie de session.
Le draft est créé mais PAS publié — Nico relit et clique « Publier » sur Substack.

Usage : python3 scripts/publish_substack.py [--dry-run]
Requiert : SUBSTACK_SID (env ou ~/.brand_factory/keys.env) = valeur du cookie
`substack.sid` (navigateur connecté à substack.com → DevTools → Cookies).
Sans cookie : warning et sortie 0 (le pipeline continue).
"""
import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUB = "https://nicoguyon.substack.com"
PAGE_URL = "https://veille-robotique.comptoiria.com"
MAX_PER_RUBRIQUE = 3  # règle éditoriale Nico : 2-3 news max par rubrique


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


def api(path, sid, payload=None, method=None):
    req = urllib.request.Request(f"{PUB}{path}",
                                 data=json.dumps(payload).encode() if payload else None,
                                 method=method or ("POST" if payload else "GET"),
                                 headers={"Cookie": f"substack.sid={sid}",
                                          "Content-Type": "application/json",
                                          "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Substack {e.code} sur {path}: {e.read().decode()[:300]}") from e


# --- Helpers ProseMirror -----------------------------------------------------

def text(s, bold=False, href=None):
    node = {"type": "text", "text": s}
    marks = []
    if bold:
        marks.append({"type": "strong"})
    if href:
        marks.append({"type": "link", "attrs": {"href": href}})
    if marks:
        node["marks"] = marks
    return node


def para(*nodes):
    return {"type": "paragraph", "content": list(nodes)}


def heading(s, level=2):
    return {"type": "heading", "attrs": {"level": level}, "content": [{"type": "text", "text": s}]}


def upload_image(url, sid):
    """Ré-héberge une image externe sur le CDN Substack. Renvoie l'URL CDN ou None."""
    try:
        return api("/api/v1/image", sid, {"image": url}).get("url")
    except Exception as e:
        print(f"  ⚠ upload image raté ({e}) — image sautée")
        return None


def image_node(cdn_url):
    return {"type": "captionedImage",
            "content": [{"type": "image2",
                         "attrs": {"src": cdn_url, "fullscreen": False, "imageSize": "normal"}}]}


# --- Construction du post ----------------------------------------------------

def fresh_only(items, edition_date):
    """Garde-fou fraîcheur : uniquement les news datées des 8 derniers jours."""
    try:
        limit = datetime.strptime(edition_date, "%Y-%m-%d") - timedelta(days=8)
    except (ValueError, TypeError):
        return items
    out = []
    for it in items:
        d = it.get("date")
        try:
            if d and datetime.strptime(d, "%Y-%m-%d") < limit:
                continue
        except ValueError:
            pass
        out.append(it)
    return out


def build_doc(data, sid, with_images=True):
    # Accroche : 5 premières lignes travaillées (newsletter_intro), fallback édito
    intro = (data.get("newsletter_intro") or data.get("edito", "")).strip()
    content = [para(text(line.strip())) for line in intro.split("\n") if line.strip()]

    if with_images:
        feats = [i for c in data.get("categories", []) for i in c.get("items", [])
                 if i.get("featured") and (i.get("media") or {}).get("image")]
        if feats:
            cdn = upload_image(feats[0]["media"]["image"], sid)
            if cdn:
                content.append(image_node(cdn))

    for cat in data.get("categories", []):
        items = fresh_only(cat.get("items", []), data.get("date"))[:MAX_PER_RUBRIQUE]
        if not items:  # une rubrique sans news est simplement omise
            continue
        content.append(heading(f'{cat.get("emoji", "")} {cat["title"]}'))
        for it in items:
            head = [text(it["title"], bold=True)]
            if it.get("company"):
                head.append(text(f'  ·  {it["company"]}'))
            content.append(para(*head))
            content.append(para(
                text(it.get("summary", "") + " "),
                text("Voir sur X →", href=it.get("url", PAGE_URL))))

    content.append(para(
        text("🎬 L'édition complète — toutes les news et les démos vidéo : "),
        text(PAGE_URL.replace("https://", ""), href=PAGE_URL)))
    return {"type": "doc", "content": content}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--update-draft", type=int, metavar="ID",
                    help="met à jour un draft existant au lieu d'en créer un nouveau")
    args = ap.parse_args()

    sid = load_key("SUBSTACK_SID")
    if not sid:
        print("⚠ SUBSTACK_SID absent — draft Substack sauté (fournir le cookie "
              "substack.sid dans ~/.brand_factory/keys.env).")
        return

    data = json.loads((ROOT / "data" / "latest.json").read_text())
    # Titre : descriptif de l'actu et impactant (rédigé par l'agent), jamais « Veille du … »
    title = data.get("newsletter_title") or f'🤖 Veille Robotique — {data.get("week_label", "")}'
    subtitle = data.get("newsletter_subtitle") or (data.get("edito", "").split(". ")[0] + ".")[:140]
    doc = build_doc(data, sid, with_images=not args.dry_run)

    if args.dry_run:
        print(title, "\n", subtitle, "\n", f"{len(doc['content'])} blocs ProseMirror")
        return

    uid = (api("/api/v1/subscription", sid) or {}).get("user_id")
    if not uid:
        sys.exit("Impossible de récupérer user_id (cookie expiré ?)")

    payload = {
        "draft_title": title,
        "draft_subtitle": subtitle,
        "draft_body": json.dumps(doc),
        "draft_bylines": [{"id": uid, "is_guest": False}],
        "audience": "everyone",
        "type": "newsletter",
    }
    if args.update_draft:
        api(f"/api/v1/drafts/{args.update_draft}", sid, payload, method="PUT")
        print(f"✓ Draft Substack mis à jour : {PUB}/publish/post/{args.update_draft}")
    else:
        draft = api("/api/v1/drafts", sid, payload)
        print(f"✓ Draft Substack créé : {PUB}/publish/post/{draft.get('id')} (à relire puis Publier)")


if __name__ == "__main__":
    main()
