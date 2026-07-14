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


def top10_html():
    f = DATA.parent / "robots.json"
    if not f.exists():
        return "", ""
    r = json.loads(f.read_text())
    scale = 190  # px par mètre
    human_h = r.get("human_height_m", 1.75)
    figures = f'''<figure class="bot human">
      <svg viewBox="0 0 60 175" style="height:{human_h * scale:.0f}px" aria-label="Humain 1,75 m">
        <circle cx="30" cy="14" r="12" fill="#D8D2C6"/>
        <path d="M30 28 C14 28 12 46 12 62 L16 108 L20 108 L20 172 L27 172 L28 110 L32 110 L33 172 L40 172 L40 108 L44 108 L48 62 C48 46 46 28 30 28 Z" fill="#D8D2C6"/>
      </svg>
      <figcaption><span class="bot-name">Humain</span><span class="bot-h">1,75 m</span></figcaption>
    </figure>'''
    for b in r["robots"]:
        h = (b.get("image_height_m") or b["height_m"]) * scale
        trend = {"↑": "▲", "↓": "▼"}.get(b.get("trend"), "")
        trend_html = f'<span class="trend">{trend}</span>' if trend else ""
        payload = esc(json.dumps({k: b.get(k) for k in
                                  ("rank", "name", "company", "score", "scores",
                                   "status", "fact", "height_m", "trend")},
                                 ensure_ascii=False))
        figures += f'''<figure class="bot" data-bot="{payload}" title="Cliquez pour le détail des notes">
      <span class="bot-rank">#{b["rank"]}</span>
      <img src="/robots/{b["slug"]}.png" alt="{esc(b["name"])}" style="height:{h:.0f}px" loading="lazy">
      <figcaption>
        <span class="bot-name">{esc(b["name"])} {trend_html}</span>
        <span class="bot-co">{esc(b["company"])} {b.get("country", "")}</span>
        <span class="bot-h">{str(b["height_m"]).replace(".", ",")} m · <b>{str(b["score"]).replace(".", ",")}</b>/10</span>
      </figcaption>
    </figure>'''
    section = f'''<section id="top10" class="cat">
  <h2>🏆 Le Top 10 des humanoïdes</h2>
  <p class="cat-intro">Les robots à l'échelle réelle, classés par notre score composite — mis à jour chaque semaine selon les news. {esc(r.get("updated", ""))}.</p>
  <div class="lineup-wrap"><div class="lineup">{figures}</div></div>
  <div id="botpanel" class="botpanel" hidden></div>
  <p class="methodo">{esc(r.get("methodology", ""))} <b>Cliquez sur un robot</b> pour déplier ses notes par critère.</p>
</section>'''
    nav_entry = '<a href="#top10">🏆 Top 10</a>'
    return section, nav_entry


def build(data):
    cats = data.get("categories", [])
    featured = [i for c in cats for i in c.get("items", []) if i.get("featured")][:3]

    top10, top10_nav = top10_html()
    nav = top10_nav + "".join(f'<a href="#{esc(c["id"])}">{esc(c.get("emoji", ""))} {esc(c["title"])}</a>' for c in cats)

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
<meta name="referrer" content="no-referrer">
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
.lineup-wrap{{overflow-x:auto;margin-top:22px;padding-bottom:6px}}
.lineup{{display:flex;align-items:flex-end;gap:26px;min-width:max-content;padding:16px 8px 0;border-bottom:3px solid var(--ink)}}
.bot{{display:flex;flex-direction:column;align-items:center;position:relative;text-align:center}}
.bot img{{width:auto;display:block;filter:drop-shadow(0 12px 16px rgba(22,19,15,.18))}}
.bot-rank{{position:absolute;top:-14px;left:50%;transform:translateX(-50%);background:var(--accent);color:#fff;font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:.78rem;padding:2px 9px;border-radius:99px;z-index:2}}
.bot figcaption{{display:flex;flex-direction:column;padding:10px 0 2px;font-size:.78rem;line-height:1.35;min-width:86px}}
.bot-name{{font-weight:700;font-family:'Space Grotesk',sans-serif;font-size:.88rem}}
.bot-co{{color:var(--muted)}}
.bot-h{{color:var(--muted)}}
.bot-h b{{color:var(--accent)}}
.trend{{color:var(--accent);font-size:.7rem}}
.bot.human svg{{display:block;opacity:.75}}
.bot.human .bot-name{{color:var(--muted);font-weight:500}}
.methodo{{margin-top:14px;font-size:.8rem;color:var(--muted);max-width:760px}}
.bot[data-bot]{{cursor:pointer;transition:transform .15s}}
.bot[data-bot]:hover{{transform:translateY(-4px)}}
.bot.active .bot-name{{color:var(--accent)}}
.botpanel{{margin-top:20px;background:var(--card);border:1px solid var(--line);border-radius:18px;padding:22px 24px;max-width:560px}}
.bp-head{{display:flex;align-items:center;gap:12px;margin-bottom:14px}}
.bp-head h3{{font-size:1.15rem}}
.bp-head h3 small{{color:var(--muted);font-weight:500;font-size:.85rem}}
.bp-score{{margin-left:auto;font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:1.5rem;color:var(--accent)}}
.bp-score small{{font-size:.85rem;color:var(--muted)}}
.crit{{display:flex;align-items:center;gap:12px;padding:5px 0;font-size:.88rem}}
.crit-name{{flex:0 0 130px;color:#3E3931}}
.crit-track{{flex:1;height:9px;background:var(--soft, #F1EDE5);border-radius:99px;overflow:hidden;background:#F1EDE5}}
.crit-bar{{display:block;height:100%;background:var(--accent);border-radius:99px}}
.crit b{{flex:0 0 30px;text-align:right;font-size:.85rem}}
.bp-fact{{margin-top:12px;font-size:.86rem;color:#55504A}}
.bp-fact em{{color:var(--muted)}}
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
{top10}
{sections}
</main>
<footer><div class="wrap">Généré automatiquement chaque semaine · données X (Twitter) · <a href="https://veille-robotique.comptoiria.com">veille-robotique.comptoiria.com</a></div></footer>
<script>
(function(){{
  var panel=document.getElementById('botpanel');
  if(!panel)return;
  var CRITS={{locomotion:'Locomotion',manipulation:'Manipulation',ia:'IA embarquée',industrialisation:'Industrialisation',momentum:'Momentum'}};
  document.querySelectorAll('.bot[data-bot]').forEach(function(el){{
    el.addEventListener('click',function(){{
      var b=JSON.parse(el.dataset.bot);
      document.querySelectorAll('.bot.active').forEach(function(a){{a.classList.remove('active')}});
      el.classList.add('active');
      var rows='';
      Object.keys(CRITS).forEach(function(k){{
        var v=(b.scores||{{}})[k];
        if(v==null)return;
        rows+='<div class="crit"><span class="crit-name">'+CRITS[k]+'</span><span class="crit-track"><span class="crit-bar" style="width:'+(v*10)+'%"></span></span><b>'+String(v).replace('.',',')+'</b></div>';
      }});
      panel.innerHTML='<div class="bp-head"><span class="badge">#'+b.rank+'</span><h3>'+b.name+' <small>'+(b.company||'')+'</small></h3><span class="bp-score">'+String(b.score).replace('.',',')+'<small>/10</small></span></div>'+rows+'<p class="bp-fact">'+(b.fact||'')+' <em>'+(b.status||'')+'</em></p>';
      panel.hidden=false;
      panel.scrollIntoView({{behavior:'smooth',block:'nearest'}});
    }});
  }});
}})();
</script>
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
