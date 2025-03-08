import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Get the database URL from Heroku environment variable
DATABASE_URL = os.environ.get("DATABASE_URL")

# Replace 'postgres://' with 'postgresql://' for SQLAlchemy compatibility
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Create engine and session factory
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()