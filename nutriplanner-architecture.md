# NutriPlanner — Architecture Technique

**Version 1.0 · Mars 2025**

---

## Table des matières

1. [Contexte du projet](#contexte-du-projet)
2. [Vue d'ensemble de l'architecture](#vue-densemble-de-larchitecture)
3. [Stack technique globale](#stack-technique-globale)
4. [Découpage des services](#découpage-des-services)
5. [Service-crawler : conception détaillée](#service-crawler--conception-détaillée)
6. [Infrastructure Docker](#infrastructure-docker)
7. [Technologies utilisées](#technologies-utilisées)
8. [Flux de données principaux](#flux-de-données-principaux)
9. [Décisions d'architecture](#décisions-darchitecture)
10. [Roadmap de développement](#roadmap-de-développement)

---

## Contexte du projet

NutriPlanner est une application de gestion de menus pour le suivi nutritionnel. Elle permet de :
- Stocker des recettes
- Gérer des aliments avec leurs poids et portions
- Générer des plannings hebdomadaires aléatoires
- Produire des listes de courses
- Crawler des recettes depuis des sites web et Instagram
- Enrichir automatiquement les données nutritionnelles via LLM

---

## Vue d'ensemble de l'architecture

### Principes directeurs

- **Microservices conteneurisés** — Chaque service applicatif tourne dans son propre container Docker, indépendant du cycle de vie des autres
- **Base de données partagée, schémas isolés** — Une seule instance PostgreSQL héberge plusieurs schémas SQL (un par service). Séparation logique sans surcoût opérationnel
- **Infrastructure mutualisée** — Redis, Elasticsearch et PostgreSQL sont des ressources d'infrastructure partagées entre les services via le réseau Docker interne
- **Scalabilité horizontale** — L'architecture Docker Compose locale est conçue pour migrer vers Kubernetes ou une plateforme cloud sans modifier le code applicatif
- **API-first** — Tous les services exposent une API REST documentée (OpenAPI/Swagger auto-générée par FastAPI)

### Couches de l'architecture

| Couche | Composants | Rôle |
|--------|-----------|------|
| **Clients** | React Web, React Native (Expo), CLI | Interfaces utilisateur |
| **Passerelle** | Nginx + FastAPI gateway | Routage, auth, rate limiting |
| **Services** | service-recipe, service-menu, service-crawler, service-llm-bridge | Logique métier |
| **Workers** | Celery + Redis broker | Tâches asynchrones (crawl, enrichissement) |
| **Data** | PostgreSQL, Redis, Elasticsearch | Persistance, cache, recherche |

---

## Stack technique globale

### Services existants

- **service-user** (port 8001) — Authentification et gestion utilisateurs
- **service-recipe** (port 8002) — CRUD recettes et ingrédients
- **service-menu** (port 8003) — Planification hebdomadaire

### Technologies communes

- **Backend** : FastAPI + SQLAlchemy async + asyncpg + Alembic
- **Base de données** : PostgreSQL dédié par service
- **Authentification** : JWT via python-jose, hachage argon2
- **Recherche** : Elasticsearch 8.11 (service-recipe)
- **Orchestration** : Docker Compose
- **CI/CD** : GitHub Actions + SonarQube
- **i18n** : Toutes les réponses API en clés de traduction

### Améliorations planifiées

| Amélioration | Statut | Priorité |
|-------------|--------|----------|
| Redis (broker Celery) | ✅ Fait | - |
| service-crawler | 🔲 À faire | Prochain |
| MinIO (stockage médias) | 🔲 À faire | Prochain |
| Celery Beat (scheduler) | 🔲 À faire | Prochain |
| API Gateway Traefik | 🔲 À faire | Après fonctionnalités |
| JWT centralisé via Gateway | 🔲 À faire | Avec Traefik |
| Observabilité (Prometheus/Loki) | 🔲 À faire | Prod |
| Structure uniforme services (repositories/) | 🔲 À faire | Refacto |

---

## Découpage des services

### Container #1 — service-recipe (port 8001)

**CRUD recettes et aliments. Gestion des portions, poids, macronutriments.**

**Stack** : FastAPI · SQLAlchemy · Pydantic v2 · Alembic

**Schema PostgreSQL** : `recipe`

**Modèles** :
- `Recipe`, `Ingredient`, `RecipeIngredient` (many-to-many avec quantité/unité)

**Endpoints** :
- `GET/POST/PUT/DELETE /recipes`
- `GET/POST/PUT/DELETE /ingredients`
- `GET /recipes/{id}/scale`

**Fonctionnalités** :
- Calcul automatique des macros par portion via agrégation SQL
- Indexation Elasticsearch déclenchée après chaque création/modification

---

### Container #2 — service-menu (port 8002)

**Planification hebdomadaire, randomisation contrainte, export liste de courses.**

**Stack** : FastAPI · SQLAlchemy · Pydantic v2 · python-docx

**Schema PostgreSQL** : `menu`

**Fonctionnalités** :
- Génération d'un échéancier 7 jours avec contraintes (pas de doublon, équilibre calorique)
- Agrégation automatique des ingrédients → liste de courses consolidée
- Export PDF et CSV de la liste de courses et du menu hebdomadaire
- Paramètres : nombre de personnes, objectif calorique, exclusions alimentaires

---

### Container #3 — service-crawler (port 8003)

**Extraction de recettes depuis sites web ou Instagram, normalisation et enrichissement.**

**Stack** : Scrapy · Playwright · Instaloader · recipe-scrapers · Celery

**Schema PostgreSQL** : `crawler`

**Pipeline** :
1. URL soumise → recipe-scrapers (sites supportés)
2. Fallback Playwright (sites JS)
3. Support Instagram via Instaloader : extraction caption + image du post
4. Normalisation vers le schéma Recipe interne avant persistance
5. File de tâches Celery — le crawl est toujours asynchrone

---

### Container #4 — service-llm-bridge (port 8004)

**Pont vers les LLM pour extraction de macros et enrichissement nutritionnel.**

**Stack** : FastAPI · OpenAI SDK · Ollama · Mistral API

**Modes** :
- **Cloud** : OpenAI GPT-4o-mini ou Mistral API (quelques centimes par recette)
- **Local** : Ollama + Llama 3.1 8B — 100% offline, aucun coût

**Fonctionnalités** :
- Prompt structuré → réponse JSON validée par Pydantic (calories, protéines, glucides, lipides)
- Fallback automatique : cloud en priorité, local si indisponible

---

## Service-crawler : conception détaillée

### Décisions de conception

- **DB** : PostgreSQL dédié (`postgres-crawler`, port 5436)
- **Zone de validation** : Visible par tous les utilisateurs
- **Broker** : Redis existant
- **Stockage médias** : MinIO
- **Scheduler** : Celery Beat (container séparé)

### Infrastructure à ajouter dans docker-compose

```yaml
- postgres-crawler → port 5436
- minio → ports 9000/9001
- service-crawler → port 8004 (FastAPI + workers Celery)
- celery-beat → container scheduler (pas de port exposé)
```

### Structure interne

```
service-crawler/
├── app/
│   ├── api/
│   │   └── routes/
│   │       ├── sources.py        # CRUD sources à surveiller
│   │       └── results.py        # zone de validation
│   ├── core/
│   │   └── config.py
│   ├── db/
│   │   └── session.py
│   ├── i18n/                     # clés de traduction
│   │   ├── fr.json
│   │   └── en.json
│   ├── models/
│   │   ├── crawl_source.py       # source à surveiller
│   │   └── crawl_result.py       # résultat brut + statut validation
│   ├── schemas/
│   │   ├── crawl_source.py
│   │   └── crawl_result.py
│   ├── services/
│   │   ├── web_service.py        # logique extraction web
│   │   ├── instagram_service.py  # logique extraction Instagram
│   │   └── recipe_mapper.py      # mapping crawl → structure recette
│   ├── repositories/
│   │   ├── source_repository.py
│   │   └── result_repository.py
│   └── main.py
├── tasks/
│   ├── web.py                    # tâche Celery crawl URL
│   ├── instagram.py              # tâche Celery crawl compte
│   └── scheduler.py              # config Celery Beat dynamique
├── celery_app.py
├── alembic/
├── alembic.ini
├── Dockerfile
├── pytest.ini
├── requirements.txt
└── sonar-project.properties
```

### Modèles de données

#### CrawlSource

```python
id: UUID
user_id: UUID                  # qui a ajouté la source
type: Enum                     # web | instagram | youtube
url: str                       # URL ou @compte
actif: bool
frequence_heures: int          # ex: 24 pour 1x/jour
heure_execution: time          # ex: 03:00
dernier_crawl: datetime
created_at: datetime
updated_at: datetime
```

#### CrawlResult

```python
id: UUID
source_id: UUID (nullable)     # FK CrawlSource (null si crawl ponctuel)
user_id: UUID (nullable)       # qui a crawlé (si manuel)
type: Enum                     # web | instagram | youtube
url_origine: str               # URL source du contenu
titre: str                     # titre extrait
contenu_brut: text             # texte extrait
images: List[str]              # liste URLs
video_url: str (nullable)      # lien vidéo si détecté
statut: Enum                   # EN_ATTENTE | VALIDÉ | REJETÉ
valide_par: UUID (nullable)
valide_le: datetime (nullable)
created_at: datetime
```

### Endpoints API

#### Sources (`/api/crawler/sources`)

- `POST /` → Ajouter une source (web ou instagram)
- `GET /` → Lister ses sources
- `GET /{id}` → Détail d'une source
- `PATCH /{id}` → Modifier fréquence / activer / désactiver
- `DELETE /{id}` → Supprimer une source
- `POST /{id}/crawl` → Déclencher un crawl manuel immédiat

#### Résultats / Zone de validation (`/api/crawler/results`)

- `GET /` → Lister tous les résultats EN_ATTENTE
- `GET /{id}` → Détail + prévisualisation contenu
- `PATCH /{id}/validate` → Valider → déclenche envoi vers service-recipe
- `PATCH /{id}/reject` → Rejeter
- `PATCH /{id}` → Modifier le contenu avant validation

### Flux complets

#### Flux 1 — Crawl web ponctuel

1. User `POST /sources` (type=web, url=...)
2. service-crawler publie tâche Celery dans Redis
3. Worker httpx/BeautifulSoup fetch la page
   - Fallback Playwright si site JS
4. Extraction : titre, texte, images
5. Stockage CrawlResult (statut: EN_ATTENTE)
6. User consulte `GET /results`
7. User `PATCH /results/{id}/validate`
8. `recipe_mapper.py` :
   - Extrait les ingrédients du texte
   - Pour chaque ingrédient : vérifie s'il existe dans service-recipe
     - Oui → récupère l'ID
     - Non → `POST /ingredients` pour le créer
   - Prépare la structure recette complète
   - `POST /recipes` vers service-recipe
9. CrawlResult → statut VALIDÉ

#### Flux 2 — Ajout compte Instagram + surveillance

1. User `POST /sources` (type=instagram, url=@compte)
2. Crawl immédiat déclenché :
   - Instaloader récupère la liste des posts existants
   - Pour chaque post : CrawlResult (statut: EN_ATTENTE)
   - Si post contient une vidéo → extraction video_url
3. Cron Celery Beat activé (défaut: 1x/jour à 03:00)
4. Chaque cycle :
   - Récupère uniquement les nouveaux posts (depuis dernier_crawl)
   - Déduplication par URL
   - Nouveaux résultats → EN_ATTENTE
5. User valide/rejette depuis `GET /results`

#### Flux 3 — Validation → service-recipe

`PATCH /results/{id}/validate` déclenche `recipe_mapper` :

**Ingrédients** :
```
Pour chaque ingrédient détecté dans le texte :
  GET /ingredients?name=xxx (service-recipe)
  ├── Trouvé  → utiliser l'ID existant
  └── Pas trouvé → POST /ingredients → récupérer le nouvel ID
```

**Structure recette envoyée à service-recipe** :
```json
{
  "titre": "...",
  "description": "...",
  "instructions": "...",
  "temps_preparation": null,
  "temps_cuisson": null,
  "portions": null,
  "source_url": "...",
  "ingredients": [
    { "ingredient_id": "X", "quantite": "...", "unite": "..." }
  ],
  "free_tags": []
}
```

### Phases d'implémentation

#### Phase 1 — Infrastructure crawler

- [ ] Ajouter postgres-crawler dans docker-compose (port 5436)
- [ ] Ajouter MinIO dans docker-compose (ports 9000/9001)
- [ ] Ajouter service-crawler dans docker-compose (port 8004)
- [ ] Ajouter celery-beat dans docker-compose
- [ ] Créer Dockerfile service-crawler
- [ ] Créer requirements.txt

#### Phase 2 — Squelette service-crawler

- [ ] Structure dossiers complète
- [ ] Config FastAPI + main.py
- [ ] Config Celery + connexion Redis
- [ ] Modèles SQLAlchemy (CrawlSource, CrawlResult)
- [ ] Migrations Alembic
- [ ] i18n (fr.json + en.json avec toutes les clés)
- [ ] Schemas Pydantic

#### Phase 3 — Crawl web

- [ ] Tâche Celery web.py (httpx + BeautifulSoup)
- [ ] Fallback Playwright (sites JS)
- [ ] Extraction titre/texte/images
- [ ] Endpoint POST /sources (type=web)
- [ ] Endpoint POST /sources/{id}/crawl (manuel)
- [ ] Stockage CrawlResult EN_ATTENTE
- [ ] Tests unitaires

#### Phase 4 — Zone de validation

- [ ] Endpoint GET /results
- [ ] Endpoint GET /results/{id}
- [ ] Endpoint PATCH /results/{id} (édition)
- [ ] Endpoint PATCH /results/{id}/reject
- [ ] Tests unitaires

#### Phase 5 — Connexion service-recipe (validation)

- [ ] recipe_mapper.py : extraction ingrédients du texte brut
- [ ] Vérification/création ingrédients dans service-recipe
- [ ] Construction payload recette
- [ ] Endpoint PATCH /results/{id}/validate
- [ ] Gestion erreurs si service-recipe indisponible
- [ ] Tests unitaires

#### Phase 6 — Crawl Instagram

- [ ] Tâche Celery instagram.py (Instaloader)
- [ ] Extraction posts : texte + images + video_url
- [ ] Déduplication par URL
- [ ] Endpoint POST /sources (type=instagram)
- [ ] Crawl initial au moment de l'ajout
- [ ] Intégration zone de validation existante
- [ ] Tests unitaires

#### Phase 7 — Scheduler configurable

- [ ] Config Celery Beat dynamique (stockée en DB)
- [ ] Cron Instagram : 1x/jour à 03:00 par défaut
- [ ] Endpoint PATCH /sources/{id} (modifier fréquence)
- [ ] Activation/désactivation sans redémarrage
- [ ] Tests unitaires

#### Phase 8 — YouTube (futur)

- [ ] Tâche Celery youtube.py (yt-dlp)
- [ ] Extraction : titre, description, lien vidéo
- [ ] Ajout type=youtube dans CrawlSource
- [ ] Même flux validation que Instagram

### Requirements service-crawler

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
sqlalchemy[asyncio]==2.0.36
asyncpg==0.29.0
pydantic-settings==2.5.2
alembic==1.13.3
pydantic[email]==2.13.0
celery==5.3.6
redis==5.0.1
httpx==0.25.2
beautifulsoup4==4.12.2
playwright==1.40.0
instaloader==4.10.3
yt-dlp==2024.1.1
minio==7.2.0
python-jose[cryptography]==3.3.0
unidecode==1.4.0
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
aiosqlite==0.20.0
```

### Points de vigilance

| Sujet | Risque | Mitigation |
|-------|--------|-----------|
| Instagram anti-bot | Ban IP | Rotation proxies en prod, respecter les délais |
| Instagram CGU | Usage limité | Calibrer selon usage personnel/professionnel |
| Celery Beat redémarrage | Perte config mémoire | Stocker la config cron en DB (django-celery-beat pattern) |
| service-recipe indisponible | Validation bloquée | Retry automatique Celery (max_retries=3) |
| Extraction ingrédients | Texte non structuré | Commencer simple (regex/NLP basique), affiner ensuite |
| Vidéos volumineuses | Stockage MinIO | Limiter la taille max, stocker uniquement le lien si possible |

---

## Infrastructure Docker

### Containers d'infrastructure

#### Container #5 — PostgreSQL 16
- **Rôle** : Source de vérité — schémas recipe, menu, crawler
- **Port** : 5432 interne uniquement (jamais exposé hôte)
- **Volumes** : persistants

#### Container #6 — Redis 7
- **Rôle** : Cache applicatif (TTL) + broker de messages pour Celery
- **Port** : 6379 interne
- **Préfixes** : clés par service

#### Container #7 — Elasticsearch 8
- **Rôle** : Index de recherche full-text sur recettes et ingrédients
- **Port** : 9200 interne
- **Index** : recipes, ingredients

#### Container #8 — Nginx
- **Rôle** : Reverse proxy — seul point d'entrée exposé vers la machine hôte
- **Ports** : 80/443 exposés → routing vers services internes

#### Container #9 — Celery Worker
- **Rôle** : Exécution des tâches asynchrones de crawl et d'enrichissement LLM
- **Consomme** : queue Redis
- **Scalabilité** : horizontale possible

#### Container #10 — Kibana (dev uniquement)
- **Rôle** : Interface d'administration Elasticsearch
- **Port** : 5601
- **Statut** : désactivé en production

### Réseau Docker interne

Tous les containers partagent un réseau bridge Docker nommé `nutriplanner_net`. Les services se joignent par nom de service DNS interne :
- `postgres:5432`
- `redis:6379`
- `elasticsearch:9200`

**Isolation** : Aucun port d'infrastructure n'est exposé vers la machine hôte — seul Nginx ouvre les ports 80 et 443.

### Structure des répertoires

```
nutriplanner/
├── services-infra/              # orchestration Docker Compose
│   ├── docker-compose.yml
│   ├── docker-compose.dev.yml
│   └── nginx/nginx.conf
├── service-recipe/              # FastAPI · schéma recipe
├── service-menu/                # FastAPI · schéma menu
├── service-crawler/             # Scrapy/Playwright · Celery
├── service-llm-bridge/          # Wrapper LLM
└── frontend/
    ├── web/                     # React + Vite
    └── mobile/                  # React Native (Expo)
```

---

## Technologies utilisées

| Catégorie | Technologie | Version | Rôle |
|-----------|------------|---------|------|
| **Backend** | Python | 3.12 | Langage principal de tous les services |
| | FastAPI | 0.115+ | Framework API REST avec OpenAPI auto-généré |
| | SQLAlchemy | 2.x | ORM async, gestion des sessions et transactions |
| | Pydantic v2 | 2.x | Validation des données et schémas HTTP |
| | Alembic | 1.x | Migrations de schémas PostgreSQL |
| **Base de données** | PostgreSQL | 16 | Source de vérité — données structurées |
| | Redis | 7 | Cache TTL et broker Celery |
| | Elasticsearch | 8.x | Recherche full-text sur recettes/ingrédients |
| **Crawling** | Scrapy | 2.x | Spider pour sites web HTML classiques |
| | Playwright (Python) | 1.x | Headless browser pour sites JS/SPA |
| | Instaloader | 4.x | Extraction de posts et captions Instagram |
| | recipe-scrapers | 14.x | Parsing structuré pour 500+ sites de recettes |
| **Async** | Celery | 5.x | Workers de tâches asynchrones (crawl, LLM) |
| **LLM** | OpenAI SDK | 1.x | GPT-4o-mini pour extraction macros (cloud) |
| | Ollama | latest | Llama 3.1 8B en local — mode offline |
| **Frontend** | React + Vite | 18 / 5 | Interface web SPA |
| | React Native (Expo) | 0.74+ | Application mobile iOS et Android |
| **Infrastructure** | Docker + Compose | 26+ | Conteneurisation et orchestration locale |
| | Nginx | 1.25+ | Reverse proxy et point d'entrée unique |

---

## Flux de données principaux

### Ajout d'une recette manuellement

1. L'utilisateur soumet la recette via le frontend
2. service-recipe valide les données (Pydantic v2)
3. Persistance dans PostgreSQL schéma `recipe`
4. Appel asynchrone à service-llm-bridge si les macros sont absentes
5. Indexation dans Elasticsearch pour la recherche

### Crawl d'une recette depuis une URL

1. L'utilisateur soumet une URL (site web ou Instagram)
2. service-crawler pousse une tâche dans la queue Celery (Redis)
3. Le worker tente recipe-scrapers → Playwright si échec
4. Pour Instagram : Instaloader extrait la caption et l'image
5. Texte brut envoyé à service-llm-bridge pour extraction des macros
6. Résultat normalisé persisté via service-recipe

### Génération du menu hebdomadaire

1. L'utilisateur configure : nombre de personnes, objectif calorique, durée
2. service-menu interroge service-recipe pour la liste des recettes disponibles
3. Algorithme de randomisation contrainte (pas de doublon, équilibre nutritionnel)
4. Calcul de la liste de courses agrégée par ingrédient
5. Export PDF/CSV disponible en téléchargement immédiat

---

## Décisions d'architecture

### SGBD — Pourquoi PostgreSQL comme source de vérité

| Critère | PostgreSQL | MongoDB | Elasticsearch seul |
|---------|-----------|---------|-------------------|
| Données relationnelles (recettes/ingrédients) | ✅ Excellent | ⚠️ Correct | ❌ Non adapté |
| JSON/schéma flexible (JSONB) | ✅ JSONB natif | ✅ Natif | ✅ Natif |
| Transactions ACID | ✅ Oui | ⚠️ Partiel | ❌ Non |
| Compatibilité SQLAlchemy | ✅ Excellente | ⚠️ ODM séparé | ❌ Non |
| Recherche full-text native | ⚠️ Basique (tsvector) | ⚠️ Limitée | ✅ Excellent |
| Complexité opérationnelle | ✅ Faible | ✅ Faible | ⚠️ Élevée seul |

**Décision** : Elasticsearch est utilisé comme index de recherche complémentaire, pas comme base principale. Les données master restent dans PostgreSQL — Elastic en est une projection optimisée pour la recherche.

### LLM — Cloud vs Local

| Critère | OpenAI / Mistral API | Ollama (local) |
|---------|---------------------|----------------|
| **Coût** | ~0.002€/recette | Gratuit |
| **Qualité d'extraction** | Très bonne | Bonne (8B) |
| **Confidentialité** | Données envoyées cloud | 100% local |
| **Latence** | 1-3s | 5-15s (CPU) |
| **Infra requise** | Aucune | 8 Go RAM min |
| **Recommandation** | Défaut (démarrage rapide) | Mode offline/prod local |

---

## Roadmap de développement

### Phase 1 — Fondations
- Setup Docker Compose : PostgreSQL, Redis, Nginx
- service-recipe : CRUD recettes et ingrédients, modèles SQLAlchemy, schémas Pydantic v2
- Migrations Alembic initiales
- Frontend web minimal (liste + formulaire de recettes)

### Phase 2 — Planification
- service-menu : algorithme de randomisation hebdomadaire
- Génération de la liste de courses agrégée
- Export PDF du menu et de la liste de courses

### Phase 3 — Crawling
- service-crawler : intégration recipe-scrapers + Playwright
- Support Instagram via Instaloader
- Queue Celery pour traitement asynchrone

### Phase 4 — Enrichissement LLM
- service-llm-bridge : OpenAI API par défaut
- Mode Ollama local en option
- Indexation Elasticsearch pour la recherche avancée

### Phase 5 — Mobile
- Application React Native (Expo) — partage de code avec le web
- Authentification utilisateur
- Synchronisation hors-ligne

---

**Document confidentiel · NutriPlanner v1.0 · Mars 2025**
