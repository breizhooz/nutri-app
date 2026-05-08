from sqlalchemy.orm import DeclarativeBase, validates
from sqlalchemy import Column, DateTime
from datetime import datetime
from app.db.base_class import Base

class AbstractModel(Base):
    __abstract__ = True

    def _generic_enum_validator(self, key, value, enum_class):
        """Généric check Enum value"""
        if value is None:
            return value
            
        allowed = {e.value for e in enum_class}
        
        # Gestion des listes ou valeurs simples
        items = value if isinstance(value, list) else [value]
        
        for item in items:
            # On vérifie si l'item est un membre de l'Enum ou sa valeur
            val_to_check = item.value if hasattr(item, 'value') else item
            if val_to_check not in allowed:
                raise ValueError(f"'{item}' n'est pas une valeur valide pour {key}.")
        return value