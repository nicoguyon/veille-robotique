#!/bin/bash
# Veille robotique — run hebdo sur le VPS Hermes (cron : jeudi 18h Europe/Paris).
# Lance l'agent Claude Code en headless ; tout le pipeline est décrit dans AGENT.md.
set -uo pipefail

REPO=/root/veille-robotique
LOG_DIR=$REPO/logs
mkdir -p "$LOG_DIR"
LOG=$LOG_DIR/run-$(date +%Y-%m-%d).log

# Clés API (synchronisées automatiquement depuis le MacBook Air toutes les 15 min)
set -a
source /root/.brand_factory/keys.env 2>/dev/null || source /etc/profile.d/comptoiria-keys.sh
set +a
# L'abonnement Claude (OAuth) doit rester actif — jamais de clé API Anthropic ici
unset ANTHROPIC_API_KEY

cd "$REPO"
git pull --rebase >>"$LOG" 2>&1

claude -p "$(cat hermes/PROMPT.md)" \
  --dangerously-skip-permissions \
  --model claude-sonnet-5 \
  >>"$LOG" 2>&1
STATUS=$?

if [ $STATUS -ne 0 ]; then
  # Alerte Telegram en cas d'échec du run
  TOKEN=$(grep '^TELEGRAM_BOT_TOKEN=' /root/.brand_factory/keys.env | cut -d= -f2)
  CHAT=$(grep '^TELEGRAM_CHAT_ID=' /root/.brand_factory/keys.env | cut -d= -f2)
  if [ -n "$TOKEN" ] && [ -n "$CHAT" ]; then
    curl -s "https://api.telegram.org/bot$TOKEN/sendMessage" \
      -d chat_id="$CHAT" \
      -d text="⚠️ Veille robotique : le run hebdo a échoué (exit $STATUS). Voir $LOG sur Hermes." >/dev/null
  fi
fi
exit $STATUS
