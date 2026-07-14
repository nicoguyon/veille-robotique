#!/usr/bin/env python3
"""Veille robotique — génère public/index.html (+ archive) depuis data/latest.json.

data/latest.json = édition éditorialisée (catégories, résumés FR, médias) produite
par l'agent après le fetch. Usage : python3 scripts/build.py
"""
import json
import html
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "latest.json"
PUB = ROOT / "public"


def fmt_n(n):
    try:
        n = int(n)
    except (TypeError, ValueError):
        return ""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}".replace(".", ",").rstrip("0").rstrip(",") + " M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}".replace(".", ",").rstrip("0").rstrip(",") + " k"
    return str(n)


def esc(s):
    return html.escape(s or "", quote=True)


def media_html(item, big=False):
    m = item.get("media") or {}
    img, vid = m.get("image"), m.get("video")
    if vid:
        poster = f' poster="{esc(img)}"' if img else ""
        return (f'<div class="card-media"><video controls preload="none" playsinline{poster}>'
                f'<source src="{esc(vid)}" type="video/mp4"></video>'
                f'<span class="media-badge">▶ démo vidéo</span></div>')
    if img:
        return (f'<div class="card-media"><a href="{esc(item.get("url"))}" target="_blank" rel="noopener">'
                f'<img src="{esc(img)}" alt="" loading="lazy"></a></div>')
    return ""


def card_html(item, big=False):
    met = item.get("metrics") or {}
    likes, views = fmt_n(met.get("likes")), fmt_n(met.get("views"))
    metrics = []
    if likes:
        metrics.append(f"❤️ {likes}")
    if views:
        metrics.append(f"👁 {views}")
    company = item.get("company")
    badge = f'<span class="badge">{esc(company)}</span>' if company else ""
    tag = item.get("tag")
    badge2 = f'<span class="badge badge-soft">{esc(tag)}</span>' if tag else ""
    handle = item.get("author_handle")
    src = f'<a class="src" href="{esc(item.get("url"))}" target="_blank" rel="noopener">@{esc(handle)} sur X →</a>' if handle else ""
    return f'''<article class="card{' card-big' if big else ''}">
  {media_html(item, big)}
  <div class="card-body">
    <div class="card-badges">{badge}{badge2}</div>
    <h3>{esc(item.get("title"))}</h3>
    <p>{esc(item.get("summary"))}</p>
    <div class="card-foot"><span class="metrics">{" · ".join(metrics)}</span>{src}</div>
  </div>
</article>'''


def build(data):
    cats = data.get("categories", [])
    featured = [i for c in cats for i in c.get("items", []) if i.get("featured")][:3]

    nav = "".join(f'<a href="#{esc(c["id"])}">{esc(c.get("emoji", ""))} {esc(c["title"])}</a>' for c in cats)

    feat_html = ""
    if featured:
        feat_html = ('<section class="featured"><h2 class="kicker">🏆 À la une cette semaine</h2>'
                     '<div class="grid grid-featured">'
                     + "".join(card_html(i, big=True) for i in featured)
                     + "</div></section>")

    sections = ""
    for c in cats:
        items = [i for i in c.get("items", []) if not i.get("featured")] or c.get("items", [])
        cards = "".join(card_html(i) for i in items)
        intro = f'<p class="cat-intro">{esc(c["intro"])}</p>' if c.get("intro") else ""
        sections += (f'<section id="{esc(c["id"])}" class="cat">'
                     f'<h2>{esc(c.get("emoji", ""))} {esc(c["title"])}</h2>{intro}'
                     f'<div class="grid">{cards}</div></section>')

    stats = data.get("stats") or {}
    stat_line = f'{stats.get("tweets_analyses", "—")} posts X analysés · {stats.get("sources", "—")} comptes suivis'

    return f'''<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex">
<title>Veille Robotique — {esc(data.get("week_label"))}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{{--bg:#FAF9F6;--ink:#16130F;--muted:#6B655C;--accent:#FF4D00;--card:#FFFFFF;--line:#EBE7DF}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:var(--bg);color:var(--ink);font-family:Inter,system-ui,sans-serif;line-height:1.6}}
h1,h2,h3,.kicker{{font-family:'Space Grotesk',sans-serif}}
.wrap{{max-width:1180px;margin:0 auto;padding:0 20px}}
header.hero{{padding:56px 0 36px;border-bottom:1px solid var(--line)}}
.hero .eyebrow{{color:var(--accent);font-weight:600;letter-spacing:.12em;text-transform:uppercase;font-size:.8rem}}
.hero h1{{font-size:clamp(2rem,5.5vw,3.4rem);line-height:1.06;margin:.35em 0 .3em}}
.hero .week{{color:var(--muted);font-size:1.05rem}}
.hero .edito{{margin-top:18px;font-size:1.12rem;max-width:760px}}
.hero .statline{{margin-top:14px;color:var(--muted);font-size:.86rem}}
nav.catnav{{position:sticky;top:0;background:rgba(250,249,246,.92);backdrop-filter:blur(8px);border-bottom:1px solid var(--line);z-index:50;overflow-x:auto;white-space:nowrap}}
nav.catnav .wrap{{display:flex;gap:6px;padding:10px 20px}}
nav.catnav a{{color:var(--ink);text-decoration:none;font-size:.88rem;font-weight:500;padding:7px 13px;border-radius:99px;border:1px solid var(--line);background:#fff}}
nav.catnav a:hover{{border-color:var(--accent);color:var(--accent)}}
section{{padding:40px 0 8px}}
h2{{font-size:1.55rem;margin-bottom:6px}}
.kicker{{font-size:1.1rem;color:var(--ink)}}
.cat-intro{{color:var(--muted);max-width:720px;margin-bottom:8px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:22px;margin-top:20px}}
.grid-featured{{grid-template-columns:repeat(auto-fit,minmax(300px,1fr))}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:18px;overflow:hidden;display:flex;flex-direction:column;transition:transform .18s,box-shadow .18s}}
.card:hover{{transform:translateY(-3px);box-shadow:0 14px 34px rgba(22,19,15,.09)}}
.card-media{{position:relative;background:#111;aspect-ratio:16/10}}
.card-media img,.card-media video{{width:100%;height:100%;object-fit:cover;display:block}}
.media-badge{{position:absolute;top:10px;left:10px;background:rgba(0,0,0,.65);color:#fff;font-size:.72rem;font-weight:600;padding:4px 9px;border-radius:99px;pointer-events:none}}
.card-body{{padding:18px 18px 16px;display:flex;flex-direction:column;gap:8px;flex:1}}
.card-badges{{display:flex;gap:6px;flex-wrap:wrap}}
.badge{{background:var(--ink);color:#fff;font-size:.7rem;font-weight:600;padding:3px 9px;border-radius:99px;letter-spacing:.03em}}
.badge-soft{{background:#F1EDE5;color:var(--muted)}}
.card h3{{font-size:1.08rem;line-height:1.3}}
.card p{{font-size:.92rem;color:#3E3931}}
.card-foot{{margin-top:auto;display:flex;justify-content:space-between;align-items:center;padding-top:8px;font-size:.82rem;color:var(--muted)}}
.src{{color:var(--accent);text-decoration:none;font-weight:600}}
footer{{margin-top:56px;padding:28px 0 40px;border-top:1px solid var(--line);color:var(--muted);font-size:.85rem}}
footer a{{color:var(--accent)}}
@media(max-width:640px){{.grid{{grid-template-columns:1fr}}section{{padding:30px 0 4px}}}}
</style>
</head>
<body>
<header class="hero"><div class="wrap">
  <div class="eyebrow">Veille hebdo · Robotique × X</div>
  <h1>🤖 Veille Robotique</h1>
  <div class="week">{esc(data.get("week_label"))}</div>
  <p class="edito">{esc(data.get("edito"))}</p>
  <div class="statline">{stat_line}</div>
</div></header>
<nav class="catnav"><div class="wrap">{nav}</div></nav>
<main class="wrap">
{feat_html}
{sections}
</main>
<footer><div class="wrap">Généré automatiquement chaque semaine · données X (Twitter) · <a href="https://veille-robotique.comptoiria.com">veille-robotique.comptoiria.com</a></div></footer>
</body>
</html>'''


def main():
    data = json.loads(DATA.read_text())
    PUB.mkdir(exist_ok=True)
    out = build(data)
    (PUB / "index.html").write_text(out)
    arch = PUB / "archives"
    arch.mkdir(exist_ok=True)
    if data.get("date"):
        (arch / f"{data['date']}.html").write_text(out)
    print(f"✓ public/index.html généré ({len(out) // 1024} Ko)")


if __name__ == "__main__":
    main()
