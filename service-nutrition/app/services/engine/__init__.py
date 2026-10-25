"""Moteur de cibles nutritionnelles — 2 couches strictement découplées.

Les cibles journalières sont calculées sur l'appareil (ou fixées par un coach) :
le serveur n'a aucune donnée corporelle (allègement RGPD, 2026-10-24).

Étape 2 (step2_user_overrides) : ajustements UI (overrides, tolérances).
Étape 3 (step3_search_query)   : critères de recherche de recettes.

Aucune logique d'une étape ne doit fuiter dans une étape voisine.
"""
