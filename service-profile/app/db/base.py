"""Point d'import centralisé pour Alembic autogenerate.

Chaque import enregistre la table correspondante dans Base.metadata. Depuis
l'allègement RGPD (2026-10-24), service-profile ne stocke ni coffre chiffré ni
donnée de santé : seul le profil nutritionnel (préférences, exclusions, cibles).
"""

from app.db.base_class import Base  # noqa: F401
from app.models.nutrition_profile import NutritionProfile  # noqa: F401
