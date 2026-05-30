"""Moteur de cibles nutritionnelles — 3 couches strictement découplées.

Étape 1 (step1_base_targets) : cibles théoriques pures (physiologie).
Étape 2 (step2_user_overrides) : fusion profil UI + garde-fous de sécurité.
Étape 3 (step3_search_query)   : construction de la requête Elasticsearch.

Aucune logique d'une étape ne doit fuiter dans une étape voisine.
"""
