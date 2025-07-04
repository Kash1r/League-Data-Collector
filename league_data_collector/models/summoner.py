"""Summoner model for storing player information."""
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship

from .base import BaseModel, SessionLocal

class Summoner(BaseModel):
    """Represents a League of Legends summoner/player."""
    
    # Riot API fields
    puuid = Column(String(78), unique=True, nullable=False, index=True)  # Riot's PUUID
    account_id = Column(String(56), nullable=True, index=True)  # Deprecated in V5 but kept for reference
    summoner_id = Column(String(63), nullable=True, index=True)  # Encrypted summoner ID
    name = Column(String(50), nullable=False, index=True)  # Summoner name
    profile_icon_id = Column(Integer, nullable=True)  # Profile icon ID
    summoner_level = Column(Integer, nullable=False, default=1)  # Summoner level
    
    # Region tracking
    region = Column(String(10), nullable=False, index=True)  # Platform ID (e.g., 'na1', 'euw1')
    
    # Relationships
    matches = relationship("Participant", back_populates="summoner")
    
    # Indexes
    __table_args__ = (
        UniqueConstraint('puuid', name='uq_summoner_puuid'),
        Index('ix_summoner_name_region', 'name', 'region', unique=True),
    )
    
    def __repr__(self):
        return f"<Summoner(name='{self.name}', level={self.summoner_level}, region='{self.region}')>"
    
    @classmethod
    def get_by_puuid(cls, session, puuid: str):
        """Get a summoner by their PUUID."""
        return session.query(cls).filter(cls.puuid == puuid).first()
    
    @classmethod
    def get_by_name_and_region(cls, session, name: str, region: str):
        """Get a summoner by their name and region."""
        return session.query(cls).filter(
            cls.name == name,
            cls.region == region.lower()
        ).first()
    
    @classmethod
    def create_or_update_from_api(cls, session, api_data: dict, region: str):
        """Create or update a summoner from Riot API data."""
        summoner = session.query(cls).filter_by(puuid=api_data['puuid']).first()
        
        if not summoner:
            summoner = cls(
                puuid=api_data['puuid'],
                region=region.lower()
            )
        
        # Update fields from API
        summoner.account_id = api_data.get('accountId')  # May be None in V5
        summoner.summoner_id = api_data.get('id')  # May be None in V5
        summoner.name = api_data['name']
        summoner.profile_icon_id = api_data.get('profileIconId')
        summoner.summoner_level = api_data.get('summonerLevel', 1)
        
        session.add(summoner)
        return summoner
