#!/usr/bin/env python3
"""Veille robotique — récupère les tweets de la semaine via Apify.

Actor : kaitoeasyapi/twitter-x-data-tweet-scraper-pay-per-result-cheapest
($0.18/1k tweets, compatible free plan — apidojo/tweet-scraper bloque le free plan).
Un run par requête ; les runs sont lancés en parallèle puis agrégés.

Sortie : data/raw-YYYY-MM-DD.json (tweets normalisés, dédupliqués, triés par engagement).
Usage : python3 scripts/fetch_tweets.py [--days 7]
Requiert : APIFY_TOKEN dans l'env ou dans ~/.brand_factory/keys.env
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
ACTOR = "kaitoeasyapi~twitter-x-data-tweet-scraper-pay-per-result-cheapest"

# Comptes constructeurs / acteurs clés de la robotique sur X (groupés par run)
BUILDER_GROUPS = [
    ["Figure_robot", "Tesla_Optimus", "UnitreeRobotics", "BostonDynamics", "1x_tech", "agilityrobotics"],
    ["apptronik", "FourierIntell", "UBTECHRobotics", "physical_int", "kscalelabs"],
    ["LimXDynamics", "NeuraRobotics", "SkildAI", "DeepRobotics_CN", "XPengMotors"],
]


def load_token():
    tok = os.environ.get("APIFY_TOKEN")
    if tok:
        return tok
    keys = Path.home() / ".brand_factory" / "keys.env"
    if keys.exists():
        for line in keys.read_text().splitlines():
            if line.startswith("APIFY_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"')
    sys.exit("APIFY_TOKEN introuvable")


def api(path, token, payload=None):
    url = f"https://api.apify.com/v2/{path}{'&' if '?' in path else '?'}token={token}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def build_jobs(since: str) -> list[dict]:
    jobs = []
    for grp in BUILDER_GROUPS:
        q = "(" + " OR ".join(f"from:{h}" for h in grp) + ")"
        jobs.append({"label": f"constructeurs:{grp[0]}…",
                     "input": {"twitterContent": q, "since": since,
                               "queryType": "Latest", "maxItems": 60}})
    jobs += [
        {"label": "humanoid-robot-top",
         "input": {"twitterContent": "humanoid robot", "since": since, "min_faves": 500,
                   "queryType": "Top", "maxItems": 50}},
        {"label": "robotics-top",
         "input": {"twitterContent": "robotics", "since": since, "min_faves": 1500,
                   "queryType": "Top", "maxItems": 30}},
        {"label": "funding-valos",
         "input": {"twitterContent": '(robot OR robotics OR humanoid) (funding OR raised OR valuation OR "Series A" OR "Series B" OR "Series C")',
                   "since": since, "min_faves": 80, "queryType": "Top", "maxItems": 40}},
        {"label": "demos-video",
         "input": {"twitterContent": "(humanoid OR robot) demo", "since": since, "min_faves": 300,
                   "queryType": "Videos", "maxItems": 40}},
    ]
    return jobs


def best_video(media_entry):
    variants = [v for v in media_entry.get("video_info", {}).get("variants", [])
                if v.get("content_type") == "video/mp4"]
    if not variants:
        return None
    return max(variants, key=lambda v: v.get("bitrate", 0)).get("url")


def parse_date(s):
    # "Tue Jul 07 12:41:02 +0000 2026" → "2026-07-07"
    try:
        return datetime.strptime(s, "%a %b %d %H:%M:%S %z %Y").strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return s


def normalize(item):
    if not item.get("id") or not item.get("url"):
        return None
    author = item.get("author") or {}
    media = []
    for m in (item.get("extendedEntities") or {}).get("media", []):
        kind = m.get("type")  # photo | video | animated_gif
        entry = {"type": kind, "image": m.get("media_url_https")}
        if kind in ("video", "animated_gif"):
            entry["video"] = best_video(m)
        media.append(entry)
    return {
        "id": str(item.get("id")),
        "url": item.get("url"),
        "date": parse_date(item.get("createdAt")),
        "text": item.get("text") or "",
        "lang": item.get("lang"),
        "likes": item.get("likeCount", 0) or 0,
        "retweets": item.get("retweetCount", 0) or 0,
        "replies": item.get("replyCount", 0) or 0,
        "views": item.get("viewCount", 0) or 0,
        "author": {
            "name": author.get("name"),
            "handle": author.get("userName"),
            "avatar": author.get("profilePicture"),
            "followers": author.get("followers"),
        },
        "media": media,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    args = ap.parse_args()

    token = load_token()
    since = (datetime.now(timezone.utc) - timedelta(days=args.days)).strftime("%Y-%m-%d")
    jobs = build_jobs(since)

    print(f"→ Lancement de {len(jobs)} runs Apify (since {since})…")
    for j in jobs:
        run = api(f"acts/{ACTOR}/runs", token, j["input"])["data"]
        j["run_id"], j["status"] = run["id"], run["status"]

    pending = set(range(len(jobs)))
    while pending:
        time.sleep(12)
        for i in list(pending):
            d = api(f"actor-runs/{jobs[i]['run_id']}", token)["data"]
            jobs[i]["status"], jobs[i]["dataset"] = d["status"], d["defaultDatasetId"]
            if d["status"] not in ("READY", "RUNNING"):
                pending.discard(i)
        print(f"  … {len(jobs) - len(pending)}/{len(jobs)} runs terminés")

    seen, tweets = set(), []
    for j in jobs:
        if j["status"] != "SUCCEEDED":
            print(f"  ⚠ run {j['label']} → {j['status']}")
            continue
        items = api(f"datasets/{j['dataset']}/items?clean=true&format=json", token)
        kept = 0
        for it in items:
            n = normalize(it)
            if n and n["id"] not in seen:
                seen.add(n["id"])
                tweets.append(n)
                kept += 1
        print(f"  ✓ {j['label']}: {kept} tweets")

    tweets.sort(key=lambda t: (t["likes"] + 2 * t["retweets"]), reverse=True)
    out = ROOT / "data" / f"raw-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"since": since, "fetched_at": datetime.now(timezone.utc).isoformat(),
                               "count": len(tweets), "tweets": tweets}, ensure_ascii=False, indent=1))
    print(f"✓ {len(tweets)} tweets uniques → {out}")


if __name__ == "__main__":
    main()
