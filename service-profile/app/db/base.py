"""Point d'import centralisé pour Alembic autogenerate.

Chaque import enregistre la table correspondante dans Base.metadata.
"""

from app.db.base_class import Base  # noqa: F401
from app.models.body_composition_snapshot import BodyCompositionSnapshot  # noqa: F401
from app.models.body_measurements_snapshot import BodyMeasurementsSnapshot  # noqa: F401
from app.models.encrypted_blob import EncryptedBlob  # noqa: F401
from app.models.excluded_food import ExcludedFood  # noqa: F401
from app.models.food_allergy import FoodAllergy  # noqa: F401
from app.models.injury import Injury  # noqa: F401
from app.models.lifestyle_profile import LifestyleProfile  # noqa: F401
from app.models.medical_condition import MedicalCondition  # noqa: F401
from app.models.medication import Medication  # noqa: F401
from app.models.nutrition_preferences import NutritionPreferences  # noqa: F401
from app.models.performance_metric import PerformanceMetric  # noqa: F401
from app.models.profile import Profile  # noqa: F401
from app.models.sports_profile import SportsProfile  # noqa: F401
