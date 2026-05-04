from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    echo=settings.DEBUG,
    pool_pre_ping=True
)

# La factory crée des sessions à la demande
AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,   # les objets restent lisibles après un commit
)

# Dépendance FastAPI — injectée dans les routes
async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session