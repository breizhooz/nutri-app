"""Traduit en français le payload openrecipes (titres, descriptions, ingrédients)
via la Claude API (Message Batches API + prompt caching).

La source openrecipes a été traduite à la machine et conserve des résidus
anglais (titres entiers, loanwords « onion/whole/baking powder », etc.).
Ce script retraduit proprement :
  - le catalogue d'ingrédients (noms),
  - les titres et descriptions de recettes.

Pourquoi Batches API : ~200 requêtes pour ~5000 ingrédients + ~2000 recettes,
non sensible à la latence -> 50 % moins cher, asynchrone. Le prompt système
(règles de traduction) est mis en cache (prompt caching) et partagé par toutes
les requêtes.

Cohérence catalogue : chaque nom d'ingrédient est traduit une seule fois ; le
catalogue est redédupliqué sur le nom FR normalisé, et chaque référence de
recette est réécrite vers le même libellé canonique -> la contrainte
« tout ingrédient référencé existe dans le catalogue » reste vraie.

Usage :
    export ANTHROPIC_API_KEY=sk-ant-...
    python scripts/translate_payload.py ../openrecipes_recipe_payload.json \
        ../openrecipes_recipe_payload.fr.json [--model claude-opus-4-8] [--dry-run]

Le script est reprenable : l'id du batch est écrit dans <sortie>.batch.json ;
relancer la commande reprend le polling au lieu de resoumettre.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import unicodedata
from collections import OrderedDict

MODEL_DEFAULT = "claude-opus-4-8"
INGREDIENTS_PER_REQUEST = 50
RECIPES_PER_REQUEST = 20

SYSTEM_PROMPT = """\
Tu es un traducteur culinaire professionnel anglais/français.
On te donne des données de recettes issues d'une traduction automatique bâclée :
elles contiennent des résidus anglais (mots isolés ou phrases entières) mêlés au
français. Ta tâche : produire un français naturel, correct et idiomatique.

Règles :
- Traduis TOUT résidu anglais en français culinaire courant.
  Exemples : onion→oignon, whole→entier, baking powder→levure chimique,
  baking soda→bicarbonate de soude, capers→câpres, panko bread crumbs→chapelure
  panko, cheese→fromage, chicken→poulet, beef→bœuf, flour→farine, sugar→sucre,
  butter→beurre, brown sugar→sucre roux, heavy cream→crème épaisse,
  boneless skinless chicken breasts→blancs de poulet, whole milk→lait entier.
- Si un terme est déjà correct en français, garde-le tel quel.
- Conserve les noms propres et marques (ex. « Dr Pepper », « Sriracha »).
- Corrige les fautes évidentes de la traduction machine (ex. « moulenu »→« moulu »,
  « sucre browned »→« sucre roux »).
- Reste fidèle au sens ; n'invente rien, n'ajoute pas d'information.
- Pour un nom d'ingrédient : renvoie un libellé court et canonique (pas de phrase).
- Garde la casse naturelle d'un libellé de recette (pas de MAJUSCULES inutiles).
- Renvoie UNIQUEMENT le JSON demandé, rien d'autre.
"""

# Schémas de sortie structurée (JSON garanti parseable).
INGREDIENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "i": {"type": "integer"},
                    "fr": {"type": "string"},
                },
                "required": ["i", "fr"],
            },
        }
    },
    "required": ["items"],
}

RECIPE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "i": {"type": "integer"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["i", "title", "description"],
            },
        }
    },
    "required": ["items"],
}


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text.lower()).strip()


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield i, seq[i : i + n]


def _msg_params(model, schema, user_text, max_tokens):
    """Construit les params d'une requête batch (système caché, thinking off)."""
    return {
        "model": model,
        "max_tokens": max_tokens,
        "thinking": {"type": "disabled"},
        "system": [
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        "output_config": {"format": {"type": "json_schema", "schema": schema}},
        "messages": [{"role": "user", "content": user_text}],
    }


def build_requests(payload, model):
    """Construit la liste des requêtes batch + les manifestes d'indexation."""
    from anthropic.types.messages.batch_create_params import Request

    requests = []

    # --- Ingrédients (catalogue) : nom unique par index ---
    ing_names = [ing["name"] for ing in payload["ingredients"]]
    for start, chunk in _chunks(ing_names, INGREDIENTS_PER_REQUEST):
        listing = "\n".join(f"{start + k}. {name}" for k, name in enumerate(chunk))
        user = (
            "Traduis ces noms d'ingrédients en français (libellé court, canonique). "
            'Réponds avec un objet {"items":[{"i":<index>,"fr":<traduction>}]} '
            "couvrant chaque index fourni.\n\n" + listing
        )
        requests.append(
            Request(
                custom_id=f"ing-{start}",
                params=_msg_params(model, INGREDIENT_SCHEMA, user, 4096),
            )
        )

    # --- Recettes : titre + description par index ---
    recs = payload["recipes"]
    for start, chunk in _chunks(recs, RECIPES_PER_REQUEST):
        blocks = []
        for k, r in enumerate(chunk):
            idx = start + k
            desc = r.get("description") or ""
            blocks.append(f"[{idx}]\nTITRE: {r['title']}\nDESCRIPTION: {desc}")
        user = (
            "Traduis en français le TITRE et la DESCRIPTION de chaque recette. "
            "Si la description est vide, renvoie une chaîne vide. "
            'Réponds avec {"items":[{"i":<index>,"title":...,"description":...}]} '
            "couvrant chaque index.\n\n" + "\n\n".join(blocks)
        )
        requests.append(
            Request(
                custom_id=f"rec-{start}",
                params=_msg_params(model, RECIPE_SCHEMA, user, 8192),
            )
        )

    return requests


def _extract_json(message):
    """Récupère le JSON d'une réponse batch (1er bloc texte)."""
    for block in message.content:
        if block.type == "text":
            return json.loads(block.text)
    raise ValueError("réponse sans bloc texte")


def collect_results(client, batch_id):
    """Récupère toutes les traductions du batch -> dicts par index."""
    ing_tr: dict[int, str] = {}
    rec_tr: dict[int, dict] = {}
    errors = 0
    for result in client.messages.batches.results(batch_id):
        if result.result.type != "succeeded":
            errors += 1
            print(f"  ! {result.custom_id}: {result.result.type}")
            continue
        try:
            data = _extract_json(result.result.message)
        except Exception as exc:  # noqa: BLE001
            errors += 1
            print(f"  ! {result.custom_id}: parse {exc}")
            continue
        if result.custom_id.startswith("ing-"):
            for it in data.get("items", []):
                fr = (it.get("fr") or "").strip()
                if fr:
                    ing_tr[int(it["i"])] = fr[:200]
        else:
            for it in data.get("items", []):
                rec_tr[int(it["i"])] = {
                    "title": (it.get("title") or "").strip(),
                    "description": (it.get("description") or "").strip(),
                }
    return ing_tr, rec_tr, errors


def apply_translations(payload, ing_tr, rec_tr):
    """Applique les traductions et redéduplique le catalogue."""
    # 1. nom original -> nom FR (fallback : garde l'original si non traduit)
    orig_names = [ing["name"] for ing in payload["ingredients"]]
    translated = {name: ing_tr.get(idx, name) for idx, name in enumerate(orig_names)}

    # 2. catalogue redédupliqué par clé FR normalisée -> libellé canonique
    canonical: "OrderedDict[str, dict]" = OrderedDict()
    for ing in payload["ingredients"]:
        fr = translated[ing["name"]]
        key = _norm(fr)
        if not key:
            continue
        if key not in canonical:
            new_ing = dict(ing)
            new_ing["name"] = fr
            canonical[key] = new_ing
    payload["ingredients"] = list(canonical.values())

    # 3. réécriture des références d'ingrédients dans chaque recette
    for r in payload["recipes"]:
        seen = set()
        new_list = []
        for ri in r["ingredients"]:
            fr = translated.get(ri["name"], ri["name"])
            key = _norm(fr)
            if key not in canonical or key in seen:
                continue
            seen.add(key)
            new_ri = dict(ri)
            new_ri["name"] = canonical[key]["name"]
            new_list.append(new_ri)
        r["ingredients"] = new_list

    # 4. titres / descriptions traduits
    for idx, r in enumerate(payload["recipes"]):
        tr = rec_tr.get(idx)
        if not tr:
            continue
        if tr.get("title"):
            r["title"] = tr["title"][:300]
        if tr.get("description"):
            r["description"] = tr["description"]
        elif r.get("description") is not None and not tr.get("description"):
            # description source vide/illisible -> on laisse telle quelle
            pass

    return payload


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source")
    ap.add_argument("output")
    ap.add_argument("--model", default=MODEL_DEFAULT)
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Construit les requêtes et affiche les compteurs sans appeler l'API.",
    )
    ap.add_argument(
        "--poll-seconds", type=int, default=60, help="Intervalle de polling du batch."
    )
    args = ap.parse_args()

    with open(args.source, "r", encoding="utf-8") as f:
        payload = json.load(f)

    requests = build_requests(payload, args.model)
    n_ing = sum(1 for r in requests if r["custom_id"].startswith("ing-"))
    n_rec = len(requests) - n_ing
    print(
        f"{len(payload['ingredients'])} ingrédients, {len(payload['recipes'])} recettes "
        f"-> {len(requests)} requêtes batch ({n_ing} ingrédients + {n_rec} recettes)."
    )

    if args.dry_run:
        print("Dry-run : aucune requête envoyée.")
        return

    import anthropic

    client = anthropic.Anthropic()  # lit ANTHROPIC_API_KEY

    sidecar = args.output + ".batch.json"
    batch_id = None
    if os.path.exists(sidecar):
        with open(sidecar) as f:
            batch_id = json.load(f).get("batch_id")
        print(f"Reprise du batch existant : {batch_id}")

    if not batch_id:
        batch = client.messages.batches.create(requests=requests)
        batch_id = batch.id
        with open(sidecar, "w") as f:
            json.dump({"batch_id": batch_id, "model": args.model}, f)
        print(f"Batch créé : {batch_id} (statut {batch.processing_status})")

    while True:
        batch = client.messages.batches.retrieve(batch_id)
        if batch.processing_status == "ended":
            break
        c = batch.request_counts
        print(
            f"  ...{batch.processing_status} "
            f"(traitées={c.processing}, ok={c.succeeded}, err={c.errored})"
        )
        time.sleep(args.poll_seconds)

    print("Batch terminé, récupération des résultats...")
    ing_tr, rec_tr, errors = collect_results(client, batch_id)
    print(
        f"Traductions : {len(ing_tr)} ingrédients, {len(rec_tr)} recettes "
        f"({errors} requête(s) en erreur)."
    )

    payload = apply_translations(payload, ing_tr, rec_tr)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(
        f"Écrit dans {args.output} : "
        f"{len(payload['recipes'])} recettes, {len(payload['ingredients'])} ingrédients."
    )
    print(f"(Tu peux supprimer le fichier de reprise {sidecar}.)")


if __name__ == "__main__":
    main()
