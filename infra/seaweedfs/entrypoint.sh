#!/bin/sh
# Entrypoint SeaweedFS (remplace MinIO).
#
# 1) Génère la config S3 (identités/credentials) À PARTIR des secrets d'env, donc
#    aucune clé n'est committée : elles viennent de
#    infra/env/secrets/platform.secrets.env (gitignoré), injecté via env_file.
# 2) Démarre master + volume + filer + gateway S3 en UN seul process (mode
#    all-in-one `weed server -s3`), adapté au mono-nœud perso.
#
# Identités :
#   - "app"       : lecture/écriture (utilisée par service-recipe, et le crawler
#                   quand son stockage médias sera implémenté).
#   - "anonymous" : lecture seule publique sur les buckets servis en HTTP. C'est
#                   le mécanisme NATIF SeaweedFS pour rendre un objet public ; il
#                   remplace l'ancien appel applicatif set_bucket_policy (que
#                   SeaweedFS supporte mal).
set -e

CONFIG=/etc/seaweedfs/s3.config.json
mkdir -p /etc/seaweedfs

cat > "$CONFIG" <<EOF
{
  "identities": [
    {
      "name": "app",
      "credentials": [
        { "accessKey": "${S3_APP_ACCESS_KEY}", "secretKey": "${S3_APP_SECRET_KEY}" }
      ],
      "actions": ["Admin", "Read", "Write", "List", "Tagging"]
    },
    {
      "name": "anonymous",
      "actions": ["Read:recipes", "Read:crawler-media"]
    }
  ]
}
EOF

exec weed server -s3 \
  -s3.config="$CONFIG" \
  -dir=/data \
  -ip.bind=0.0.0.0 \
  -master.volumeSizeLimitMB=1024
