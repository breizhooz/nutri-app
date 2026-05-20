"""Énumérations du service-profile.

Chaque membre expose i18n_key() pour la résolution de traduction
et label(locale) pour le libellé traduit direct.
"""
import enum
import re


def _camel_to_snake(name: str) -> str:
    """Convertit CamelCase en snake_case pour construire les préfixes i18n."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


class TranslatableEnum(str, enum.Enum):
    """Classe de base pour les enums traduisibles.

    Convention : clé i18n = snake_case(NomClasse).valeur
    Exemple : BiologicalSex.MALE → "biological_sex.male"
    La valeur courte ("male") est ce qui est stocké en base.
    """

    def i18n_key(self) -> str:
        """Retourne la clé i18n complète : préfixe_classe.valeur."""
        prefix = _camel_to_snake(self.__class__.__name__)
        return f"{prefix}.{self.value}"

    def label(self, locale: str = "fr") -> str:
        """Retourne le libellé traduit dans la locale demandée."""
        from app.i18n import t
        return t.get(self.i18n_key(), locale)


class BiologicalSex(TranslatableEnum):
    """Sexe biologique — indispensable pour les formules métaboliques (Harris-Benedict, Mifflin-St Jeor)."""

    MALE = "male"
    FEMALE = "female"
    NOT_SPECIFIED = "not_specified"


class PracticeLevel(TranslatableEnum):
    """Niveau de pratique sportive."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    COMPETITIVE = "competitive"


class ActivityLevel(TranslatableEnum):
    """Niveau d'activité professionnelle / quotidienne hors sport (NEAT)."""

    SEDENTARY = "sedentary"
    LIGHT = "light"
    MODERATE = "moderate"
    HEAVY = "heavy"
    VERY_HEAVY = "very_heavy"


class StressLevel(TranslatableEnum):
    """Niveau de stress perçu — impacte le cortisol et la récupération."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class Chronotype(TranslatableEnum):
    """Chronotype circadien — influe sur le métabolisme et la fenêtre anabolique."""

    MORNING = "morning"
    INTERMEDIATE = "intermediate"
    EVENING = "evening"


class AlcoholFrequency(TranslatableEnum):
    """Fréquence de consommation d'alcool."""

    NEVER = "never"
    OCCASIONAL = "occasional"
    MODERATE = "moderate"
    REGULAR = "regular"


class DietType(TranslatableEnum):
    """Type de régime alimentaire suivi."""

    OMNIVORE = "omnivore"
    VEGETARIAN = "vegetarian"
    VEGAN = "vegan"
    PESCATARIAN = "pescatarian"
    KETO = "keto"
    HALAL = "halal"
    KOSHER = "kosher"
    NO_PORK = "no_pork"
    OTHER = "other"


class MainGoal(TranslatableEnum):
    """Objectif nutritionnel principal — pilote la répartition des macronutriments."""

    WEIGHT_LOSS = "weight_loss"
    MUSCLE_GAIN = "muscle_gain"
    BODY_RECOMPOSITION = "body_recomposition"
    SPORTS_PERFORMANCE = "sports_performance"
    MAINTENANCE = "maintenance"


class CookingLevel(TranslatableEnum):
    """Niveau de compétence en cuisine."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class CookingTime(TranslatableEnum):
    """Temps disponible pour la cuisine par repas."""

    QUICK = "quick"
    MODERATE = "moderate"
    EXTENDED = "extended"


class CookingFor(TranslatableEnum):
    """Contexte de préparation des repas."""

    SOLO = "solo"
    COUPLE = "couple"
    FAMILY = "family"
    MEAL_PREP = "meal_prep"


class MedicalCategory(TranslatableEnum):
    """Catégorie médicale d'une pathologie."""

    METABOLIC = "metabolic"
    DIGESTIVE = "digestive"
    CARDIOVASCULAR = "cardiovascular"
    HORMONAL = "hormonal"
    OTHER = "other"


class AllergySeverity(TranslatableEnum):
    """Niveau de sévérité d'une réaction alimentaire."""

    INTOLERANCE = "intolerance"
    ALLERGY = "allergy"