import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Get the database URL from Heroku environment variable
DATABASE_URL = os.environ.get("DATABASE_URL")

# Replace 'postgres://' with 'postgresql+asyncpg://' for async compatibility
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)

# Create async engine
async_engine = create_async_engine(DATABASE_URL, echo=True)

# Async session factory
async_session = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)

# Dependency to get async DB session
async def get_async_db():
    async with async_session() as session:
        yield session