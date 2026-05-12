from sqlalchemy import Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base_class import Base
from datetime import datetime


class AbstractModel(Base):
    __abstract__ = True

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    def _generic_enum_validator(self, key, value, enum_class):
        if value is None:
            return value
        allowed = {e.value for e in enum_class}
        items = value if isinstance(value, list) else [value]
        for item in items:
            val_to_check = item.value if hasattr(item, "value") else item
            if val_to_check not in allowed:
                raise ValueError(f"'{item}' n'est pas une valeur valide pour {key}.")
        return value