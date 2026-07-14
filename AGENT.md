# Agent de veille robotique — mode d'emploi hebdomadaire

Tu es l'agent de veille robotique de Nico. Chaque semaine, tu produis l'édition de
la veille : les principales news robotique de la semaine repérées sur X (Twitter),
catégorisées, publiées sur https://veille-robotique.comptoiria.com et envoyées par
email. **Tout est en français** (accents corrects obligatoires).

## Pipeline (dans l'ordre, ne saute aucune étape)

### 1. Récupérer les tweets de la semaine

```bash
python3 scripts/fetch_tweets.py --days 7
```

Sortie : `data/raw-YYYY-MM-DD.json` (~200-350 tweets normalisés avec métriques et
médias). Requiert `APIFY_TOKEN` dans l'environnement. Si un ou deux runs Apify
échouent, continue avec ce qui a réussi ; si TOUT échoue, envoie quand même un
email d'alerte via Resend expliquant la panne et arrête-toi.

### 2. Éditorialiser → `data/latest.json`

Lis le raw JSON et rédige l'édition. C'est TON travail éditorial — pas un simple
mapping :

- **Sélectionne** ~20-35 news réelles. Écarte : spam, shitposts, memes, comptes
  crypto, tweets sans substance, doublons d'une même actu (garde la meilleure
  source, de préférence le compte officiel du constructeur).
- **Regroupe** par catégories FIXES (ids stables) :
  - `constructeurs` 🤖 « Constructeurs & humanoïdes » — annonces produits,
    nouveaux robots, mises à jour hardware/software des fabricants.
  - `marche` 💰 « Marché, levées & valorisations » — levées de fonds, valos,
    contrats, chiffres de production, analyses de marché.
  - `demos` 🎬 « Démos de la semaine » — les vidéos les plus impressionnantes
    (privilégie les items qui ont `media.video`).
  - `recherche` 🧠 « Recherche & IA embarquée » — papiers, modèles
    fondation robotique (VLA), labos.
  - `industrie` 🏭 « Industrie & déploiements » — robots en production réelle,
    usines, logistique, clients.
  - Une catégorie vide est omise.
- **Rédige en français** : `title` (accroche courte factuelle), `summary`
  (2-3 phrases : le quoi, le pourquoi c'est important, les chiffres).
- **Marque `"featured": true`** sur les 3 news majeures de la semaine.
- **Pour chaque news featured, rédige aussi `"x_post"`** : le texte du post X
  (≤ 230 caractères, français, factuel avec les chiffres marquants, 1 emoji en
  tête, SANS lien ni hashtags — `scripts/post_x.py` ajoute le lien newsletter).
- **Rédige `"x_viral"`** (champ racine du JSON) : LE post X « stylé viral » de la
  semaine — hook percutant en 1re ligne, puis 3-4 lignes « → fait + chiffre »,
  chute courte. ≤ 250 caractères hors lien, pas de hashtags. Il sera créé en
  DRAFT Late pour validation par Nico (jamais publié directement).
- **Édito** : 2-3 phrases qui résument la tendance de la semaine.

### 2 bis. Archiver les news dans Supabase

```bash
python3 scripts/store_news.py
```

(Upsert de toutes les news de l'édition dans la table `robotics_news` —
historique permanent. Requiert `SUPABASE_VEILLE_SERVICE_KEY` ; si absente, le
script saute l'étape avec un warning.)

### 2 ter. Entretenir le Top 10 des humanoïdes (`data/robots.json`)

La page affiche un classement permanent des 10 meilleurs humanoïdes du marché,
détourés et à l'échelle (`public/robots/*.png`). **Chaque semaine, réévalue ce
classement en fonction des news** :

- Ajuste les `score` (composite : locomotion, manipulation, IA embarquée,
  industrialisation, momentum) quand une news le justifie (démo majeure,
  déploiement réel, jalon de production). Mets `trend` à `↑`/`↓`/`=` selon le
  mouvement de la semaine, et actualise `fact` (le fait marquant) et `status`.
- Re-trie `rank` par score décroissant et mets `updated` à la date du jour.
- Si un nouveau robot mérite d'entrer dans le Top 10 : ajoute son entrée
  (nom, hauteur réelle en m) et crée son image détourée → trouve une photo
  full-body officielle, détoure-la via fal.ai birefnet
  (`POST https://fal.run/fal-ai/birefnet/v2`, header `Authorization: Key $FAL_KEY`,
  body `{"image_url": "data:image/jpeg;base64,…"}`), trim la transparence (PIL
  `getbbox`), enregistre dans `public/robots/<slug>.png`. Retire le sortant.
- `image_height_m` (optionnel) = hauteur réelle représentée par le PNG si la
  pose n'est pas parfaitement debout (ex. figure-03 fléchi) — c'est ce champ
  qui pilote l'échelle d'affichage.
- ⚠️ Améliorations d'assets en attente : remplacer `figure-03.png` (pose
  fléchie) et `optimus.png` (micro-watermark sur le torse) dès qu'une meilleure
  photo officielle full-body existe.
- Ne change JAMAIS un score sans justification dans les news de la semaine.

Format exact de `data/latest.json` (consommé par `scripts/build.py`) :

```json
{
  "date": "YYYY-MM-DD",
  "week_label": "Semaine du 7 au 14 juillet 2026",
  "edito": "…",
  "stats": {"tweets_analyses": 312, "sources": 21},
  "categories": [
    {
      "id": "constructeurs", "emoji": "🤖", "title": "Constructeurs & humanoïdes",
      "intro": "1 phrase optionnelle",
      "items": [
        {
          "featured": true,
          "title": "…", "summary": "…",
          "company": "Figure", "tag": "Humanoïde",
          "date": "2026-07-13",
          "url": "https://x.com/…",
          "author_handle": "Figure_robot",
          "metrics": {"likes": 12000, "views": 2100000},
          "media": {"type": "video", "image": "https://pbs.twimg.com/…", "video": "https://video.twimg.com/….mp4"}
        }
      ]
    }
  ]
}
```

`media` : reprends `image` (thumbnail) et `video` (mp4) du raw. `company` : le
constructeur concerné (Figure, Unitree, Tesla, Boston Dynamics, 1X, Agility,
Apptronik, Fourier, UBTech, XPeng, …) quand identifiable, sinon omets.

Copie aussi le fichier en archive : `data/YYYY-MM-DD.json`.

### 3. Générer la page

```bash
python3 scripts/build.py
```

Sortie : `public/index.html` + `public/archives/YYYY-MM-DD.html`. Ouvre le HTML
généré et vérifie qu'il contient bien les sections et des médias.

### 4. Déployer sur Vercel

```bash
# le dossier .vercel n'est pas versionné : lier d'abord le projet (idempotent)
vercel link --yes --token "$VERCEL_TOKEN" --scope nicoguyon-gmailcoms-projects --project veille-robotique
vercel --prod --yes --token "$VERCEL_TOKEN"
```

(projet Vercel `veille-robotique`, domaine de projet
`veille-robotique.comptoiria.com` — déjà configuré, suit les redeploys ;
si le CLI vercel n'est pas installé : `npm i -g vercel`).

### 5. Programmer les posts X (teasing, opt-out)

```bash
python3 scripts/post_x.py
```

(API Late → compte X `@nico16184`, requiert `LATE_API_KEY`. Programme un post
par news featured, étalés : **+2 h** (fenêtre de veto pour Nico), +22 h, +46 h.
Chaque post reprend le `x_post` rédigé à l'étape 2 et renvoie vers la page.
Vérifie dans la sortie que les posts sont bien `scheduled` ; Late renvoie
parfois un 500 transitoire, le script retry déjà tout seul. Le script écrit
`data/x_posts_scheduled.json`, consommé par l'email.)

### 6. Envoyer l'email récap

```bash
python3 scripts/send_email.py
```

(Resend → nicoguyon@gmail.com : top news + lien page + **section « tweets
programmés »** avec heures de départ, pour que Nico puisse les modifier/annuler
sur getlate.dev avant publication. À lancer APRÈS post_x.py.)

### 7. Créer le brouillon Substack

```bash
python3 scripts/publish_substack.py
```

(Crée le post hebdo en BROUILLON sur https://nicoguyon.substack.com — Nico
relit et publie lui-même. Requiert `SUBSTACK_SID` (cookie de session) ; si la
clé est absente, le script saute l'étape avec un warning, continue le pipeline.
Ne JAMAIS publier automatiquement sur Substack.)

### 8. Commit & push

```bash
git add -A && git commit -m "Édition du YYYY-MM-DD" && git push
```

## Règles

- Page = fond clair, déjà géré par le template. Ne modifie pas le design sans
  demande de Nico.
- Jamais d'édition vide : s'il y a peu de matière, réduis le nombre de news mais
  publie quand même.
- Les métriques citées (likes, vues) viennent du raw, ne les invente pas.
- Si `XAI_API_KEY` a de nouveau des crédits (test :
  `curl -s https://api.x.ai/v1/responses …` ne renvoie plus permission-denied),
  tu peux enrichir l'édito avec Grok x_search, mais Apify reste la source des
  tweets/médias.
