import uuid

from sqlalchemy import Float, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class UnitConversion(Base):
    __tablename__ = "unit_conversions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slug: Mapped[str] = mapped_column(
        String(200), unique=True, nullable=False, index=True
    )
    unite: Mapped[str] = mapped_column(String(50), nullable=False)
    aliment_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    grammes: Mapped[float] = mapped_column(Float, nullable=False)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)