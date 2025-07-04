"""Database connection and initialization."""
import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, scoped_session

from .config import settings
from .models.base import Base, engine, SessionLocal, init_db

# Set up logging
logger = logging.getLogger(__name__)

# Enable SQLite foreign key support if using SQLite
if 'sqlite' in settings.DATABASE_URL:
    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

def get_db() -> Generator:
    """Dependency function to get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@contextmanager
def get_db_session():
    """Context manager for database sessions."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database error: {str(e)}")
        raise
    finally:
        session.close()

def create_tables():
    """Create all database tables."""
    logger.info("Creating database tables...")
    init_db()
    logger.info("Database tables created successfully.")

def drop_tables():
    """Drop all database tables. Use with caution!"""
    logger.warning("Dropping all database tables...")
    Base.metadata.drop_all(bind=engine)
    logger.warning("All database tables dropped.")

def reset_database():
    """Reset the database by dropping and recreating all tables."""
    logger.warning("Resetting database...")
    drop_tables()
    create_tables()
    logger.info("Database reset complete.")

# Initialize the database when this module is imported
create_tables()
