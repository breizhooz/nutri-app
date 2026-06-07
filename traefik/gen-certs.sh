#!/usr/bin/env bash
# Génère le certificat HTTPS de dev (mkcert) pour les sous-domaines *.localhost.
#
# IMPORTANT : on liste les hôtes EXPLICITEMENT. Le wildcard "*.localhost" est
# REFUSÉ par OpenSSL et les navigateurs (un wildcard exige >= 2 labels après
# l'étoile ; "*.localhost" n'en a qu'un). On le garde en bonus, mais ce sont les
# SAN explicites ci-dessous qui font foi. Ajouter ici tout nouveau sous-domaine.
#
# Prérequis (une seule fois par machine) :
#   - installer mkcert : https://github.com/FiloSottile/mkcert
#   - installer la CA locale de confiance :  mkcert -install
#
# Usage :  ./traefik/gen-certs.sh
set -euo pipefail

CERT_DIR="$(cd "$(dirname "$0")" && pwd)/certs"
mkdir -p "$CERT_DIR"

if ! command -v mkcert >/dev/null 2>&1; then
  echo "❌ mkcert introuvable. Installe-le puis lance: mkcert -install" >&2
  exit 1
fi

# Hôtes desservis par Traefik (cf. labels docker-compose + fichiers dynamiques).
HOSTS=(
  "localhost"
  "*.localhost"            # bonus / fallback (non suffisant seul)
  "api.localhost"
  "api-users.localhost"
  "api-recipe.localhost"
  "api-menu.localhost"
  "api-nutrition.localhost"
  "api-crawler.localhost"
  "api-profile.localhost"
  "api-notification.localhost"
  "traefik.localhost"
  "grafana.localhost"
  "prometheus.localhost"
  "loki.localhost"
  "tempo.localhost"
)

mkcert \
  -cert-file "$CERT_DIR/_wildcard.localhost.pem" \
  -key-file  "$CERT_DIR/_wildcard.localhost-key.pem" \
  "${HOSTS[@]}"

echo "✅ Certs générés dans $CERT_DIR"
echo "   Relance Traefik :  docker compose up -d traefik"
