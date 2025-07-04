"""Base database models and configuration."""
from datetime import datetime
from sqlalchemy import create_engine, Column, DateTime, Integer, MetaData
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import StaticPool

from ..config import settings

# Use a consistent naming convention for constraints
convention = {
    "ix": 'ix_%(column_0_label)s',
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

# Create SQLAlchemy engine with connection pooling
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    poolclass=StaticPool if "sqlite" in settings.DATABASE_URL else None
)

# Create session factory
SessionLocal = scoped_session(
    sessionmaker(autocommit=False, autoflush=False, bind=engine)
)

# Create base class for all models
Base = declarative_base(metadata=MetaData(naming_convention=convention))

class TimestampMixin:
    """Mixin that adds timestamp fields to models."""
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class BaseModel(Base, TimestampMixin):
    """Base model with common fields and methods."""
    __abstract__ = True
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    @declared_attr
    def __tablename__(cls):
        """Generate __tablename__ automatically.
        
        Convert CamelCase class name to snake_case table name.
        """
        return ''.join(['_'+i.lower() if i.isupper() else i for i in cls.__name__]).lstrip('_')
    
    def to_dict(self):
        """Convert model instance to dictionary."""
        return {
            c.name: getattr(self, c.name) 
            for c in self.__table__.columns
        }
    
    @classmethod
    def get_by_id(cls, session, id):
        """Get a record by ID."""
        return session.query(cls).filter(cls.id == id).first()
    
    def save(self, session):
        """Save the current instance to the database."""
        try:
            session.add(self)
            session.commit()
            session.refresh(self)
            return self
        except Exception as e:
            session.rollback()
            raise e
    
    def delete(self, session):
        """Delete the current instance from the database."""
        try:
            session.delete(self)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e


def get_db_session():
    """Get a database session with automatic cleanup.
    
    Yields:
        Session: A SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize the database by creating all tables."""
    Base.metadata.create_all(bind=engine)
