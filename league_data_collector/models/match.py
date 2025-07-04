"""Models for storing match and participant data."""
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, BigInteger, Boolean, 
    Float, JSON, ForeignKey, DateTime, Index, Text, UniqueConstraint
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from .base import BaseModel, SessionLocal

class Match(BaseModel):
    """Represents a League of Legends match."""
    
    # Match identification
    match_id = Column(String(100), unique=True, nullable=False, index=True)  # Riot's match ID
    platform_id = Column(String(10), nullable=False, index=True)  # Platform ID (e.g., 'NA1')
    game_id = Column(BigInteger, nullable=True, index=True)  # Game ID (deprecated in V5)
    game_version = Column(String(50), nullable=True)  # Game version (e.g., '13.1.123.1234')
    
    # Match metadata
    game_creation = Column(DateTime, nullable=True)  # When the game was created
    game_duration = Column(Integer, nullable=False)  # Game duration in seconds
    game_mode = Column(String(50), nullable=True)  # Game mode (e.g., 'CLASSIC')
    game_type = Column(String(50), nullable=True)  # Game type (e.g., 'MATCHED_GAME')
    map_id = Column(Integer, nullable=True)  # Map ID
    queue_id = Column(Integer, nullable=True, index=True)  # Queue ID (e.g., 420 for Ranked Solo/Duo)
    
    # Tournament data
    tournament_code = Column(String(100), nullable=True)  # Tournament code if applicable
    
    # Relationships
    participants = relationship("Participant", back_populates="match")
    teams = relationship("Team", back_populates="match")
    timeline = relationship("MatchTimeline", back_populates="match", uselist=False, cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        UniqueConstraint('match_id', name='uq_match_id'),
        Index('ix_match_queue_creation', 'queue_id', 'game_creation'),
    )
    
    def __repr__(self):
        return f"<Match(id={self.match_id}, duration={self.game_duration}s, queue={self.queue_id})>"
    
    @classmethod
    def get_by_match_id(cls, session, match_id: str):
        """Get a match by its Riot match ID."""
        return session.query(cls).filter(cls.match_id == match_id).first()
    
    @classmethod
    def create_or_update_from_api(cls, session, api_data: dict):
        """Create or update a match from Riot API data."""
        match = session.query(cls).filter_by(match_id=api_data['metadata']['matchId']).first()
        
        if not match:
            match = cls(
                match_id=api_data['metadata']['matchId'],
                platform_id=api_data['info'].get('platformId', '').upper(),
                game_id=api_data['info'].get('gameId'),
                game_version=api_data['info'].get('gameVersion'),
                game_creation=datetime.fromtimestamp(api_data['info']['gameCreation'] / 1000) if 'gameCreation' in api_data['info'] else None,
                game_duration=api_data['info']['gameDuration'],
                game_mode=api_data['info'].get('gameMode'),
                game_type=api_data['info'].get('gameType'),
                map_id=api_data['info'].get('mapId'),
                queue_id=api_data['info'].get('queueId'),
                tournament_code=api_data['info'].get('tournamentCode')
            )
            session.add(match)
        
        return match

class Team(BaseModel):
    """Represents a team in a match."""
    
    match_id = Column(String(100), ForeignKey('match.match_id', ondelete='CASCADE'), nullable=False)
    team_id = Column(Integer, nullable=False)  # 100 for blue, 200 for red
    win = Column(Boolean, nullable=False)  # Whether the team won
    first_blood = Column(Boolean, nullable=True)
    first_tower = Column(Boolean, nullable=True)
    first_inhibitor = Column(Boolean, nullable=True)
    first_baron = Column(Boolean, nullable=True)
    first_dragon = Column(Boolean, nullable=True)
    first_rift_herald = Column(Boolean, nullable=True)
    tower_kills = Column(Integer, nullable=True)
    inhibitor_kills = Column(Integer, nullable=True)
    baron_kills = Column(Integer, nullable=True)
    dragon_kills = Column(Integer, nullable=True)
    rift_herald_kills = Column(Integer, nullable=True)
    
    # Bans (stored as JSON for flexibility)
    bans = Column(JSON, nullable=True)
    
    # Relationships
    match = relationship("Match", back_populates="teams")
    
    # Indexes
    __table_args__ = (
        UniqueConstraint('match_id', 'team_id', name='uq_team_match_team'),
    )
    
    def __repr__(self):
        return f"<Team(match={self.match_id}, team_id={self.team_id}, win={self.win})>"

class Participant(BaseModel):
    """Represents a participant in a match."""
    
    # Foreign keys
    match_id = Column(String(100), ForeignKey('match.match_id', ondelete='CASCADE'), nullable=False, index=True)
    summoner_puuid = Column(String(78), ForeignKey('summoner.puuid', ondelete='CASCADE'), nullable=True)
    
    # Participant info
    participant_id = Column(Integer, nullable=False)  # 1-10
    team_id = Column(Integer, nullable=False)  # 100 (blue) or 200 (red)
    champion_id = Column(Integer, nullable=False)
    champion_name = Column(String(50), nullable=True)
    champion_level = Column(Integer, nullable=True)
    
    # Summoner info
    summoner_name = Column(String(50), nullable=True)
    summoner_level = Column(Integer, nullable=True)
    profile_icon = Column(Integer, nullable=True)
    
    # Stats
    kills = Column(Integer, nullable=False, default=0)
    deaths = Column(Integer, nullable=False, default=0)
    assists = Column(Integer, nullable=False, default=0)
    kda = Column(Float, nullable=True)
    
    # Damage
    total_damage_dealt = Column(Integer, nullable=True)
    total_damage_taken = Column(Integer, nullable=True)
    damage_dealt_to_champions = Column(Integer, nullable=True)
    damage_dealt_to_objectives = Column(Integer, nullable=True)
    damage_self_mitigated = Column(Integer, nullable=True)
    magic_damage_dealt = Column(Integer, nullable=True)
    magic_damage_dealt_to_champions = Column(Integer, nullable=True)
    physical_damage_dealt = Column(Integer, nullable=True)
    physical_damage_dealt_to_champions = Column(Integer, nullable=True)
    physical_damage_taken = Column(Integer, nullable=True)
    true_damage_dealt = Column(Integer, nullable=True)
    true_damage_dealt_to_champions = Column(Integer, nullable=True)
    
    # Gold and CS
    gold_earned = Column(Integer, nullable=True)
    gold_spent = Column(Integer, nullable=True)
    total_minions_killed = Column(Integer, nullable=True)
    neutral_minions_killed = Column(Integer, nullable=True)
    
    # Game state
    game_ended_in_early_surrender = Column(Boolean, nullable=True)
    game_ended_in_surrender = Column(Boolean, nullable=True)
    
    # Vision
    vision_score = Column(Integer, nullable=True)
    vision_wards_bought = Column(Integer, nullable=True)
    wards_placed = Column(Integer, nullable=True)
    wards_killed = Column(Integer, nullable=True)
    detector_wards_placed = Column(Integer, nullable=True)
    sight_wards_bought_in_game = Column(Integer, nullable=True)
    
    # Structures
    inhibitors_lost = Column(Integer, nullable=True)  # Number of inhibitors lost by the participant's team
    turrets_lost = Column(Integer, nullable=True)  # Number of turrets lost by the participant's team
    
    # Items
    item0 = Column(Integer, nullable=True)
    item1 = Column(Integer, nullable=True)
    item2 = Column(Integer, nullable=True)
    item3 = Column(Integer, nullable=True)
    item4 = Column(Integer, nullable=True)
    item5 = Column(Integer, nullable=True)
    item6 = Column(Integer, nullable=True)  # Trinket
    
    # Summoner spells
    summoner1_id = Column(Integer, nullable=True)  # D/Flash
    summoner2_id = Column(Integer, nullable=True)  # F/Other
    
    # Runes
    primary_style = Column(Integer, nullable=True)  # Primary rune tree
    sub_style = Column(Integer, nullable=True)      # Secondary rune tree
    
    # Perks (runes) - stored as JSON for flexibility
    perks = Column(JSON, nullable=True)
    
    # Position/Role
    team_position = Column(String(20), nullable=True)  # TOP, JUNGLE, MIDDLE, BOTTOM, UTILITY, NONE
    lane = Column(String(20), nullable=True)          # TOP, JUNGLE, MIDDLE, BOTTOM, NONE
    role = Column(String(20), nullable=True)          # DUO, CARRY, SUPPORT, etc.
    
    # Win status
    win = Column(Boolean, nullable=False)
    
    # Game stats
    first_blood_kill = Column(Boolean, nullable=True)
    first_blood_assist = Column(Boolean, nullable=True)
    first_tower_kill = Column(Boolean, nullable=True)
    first_tower_assist = Column(Boolean, nullable=True)
    
    # Multi-kills
    double_kills = Column(Integer, nullable=True)
    triple_kills = Column(Integer, nullable=True)
    quadra_kills = Column(Integer, nullable=True)
    penta_kills = Column(Integer, nullable=True)
    
    # Objectives
    turret_kills = Column(Integer, nullable=True)
    inhibitor_kills = Column(Integer, nullable=True)
    
    # Crowd control
    time_ccing_others = Column(Integer, nullable=True)  # Time spent CCing others (in seconds)
    total_time_cc_dealt = Column(Integer, nullable=True)  # Total duration of CC dealt (in seconds)
    
    # Additional stats (stored as JSON for flexibility)
    challenges = Column(JSON, nullable=True)
    
    # Relationships
    match = relationship("Match", back_populates="participants")
    summoner = relationship("Summoner", back_populates="matches")
    
    # Indexes
    __table_args__ = (
        UniqueConstraint('match_id', 'participant_id', name='uq_participant_match_participant'),
        Index('ix_participant_champion', 'champion_id'),
        Index('ix_participant_team_position', 'team_position'),
    )
    
    def __repr__(self):
        return f"<Participant(match={self.match_id}, summoner={self.summoner_name}, champion={self.champion_name})>"
    
    @property
    def kda_ratio(self) -> float:
        """Calculate KDA ratio."""
        if self.deaths == 0:
            return float(self.kills + self.assists)
        return (self.kills + self.assists) / self.deaths
    
    @property
    def kill_participation(self, match: 'Match' = None) -> float:
        """Calculate kill participation percentage."""
        if not match:
            return 0.0
            
        # Get total team kills
        team_kills = sum(
            p.kills for p in match.participants 
            if p.team_id == self.team_id and p.participant_id != self.participant_id
        ) + self.kills
        
        if team_kills == 0:
            return 0.0
            
        return (self.kills + self.assists) / team_kills * 100
