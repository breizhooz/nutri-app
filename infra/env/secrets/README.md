# Secrets d'environnement — JAMAIS committés

Ce répertoire contient les fichiers `*.secrets.env`, gitignorés (cf. `.gitignore` racine).
Chargés en **dernier** dans la chaîne `env_file` de chaque service : ils gagnent
sur `platform.env` et `services/<svc>.env`.

| Fichier | Consommé par |
|---|---|
| `platform.secrets.env` | postgres (initdb), seaweedfs (S3), grafana, postgres-exporter, flower — et l'interpolation `${...}` de Compose via le symlink `.env` à la racine |
| `<svc>.secrets.env` | le service métier + ses workers celery |

Sur un poste neuf : copier les `.env.example` (générés en phase 3 par
`gen-env-examples.py`) et remplir les valeurs.
