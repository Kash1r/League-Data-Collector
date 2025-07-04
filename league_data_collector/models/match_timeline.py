"""Models for storing match timeline data."""
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, BigInteger, Boolean, 
    Float, JSON, ForeignKey, DateTime, Index, Text, UniqueConstraint
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func

from .base import BaseModel, SessionLocal

class MatchTimeline(BaseModel):
    """Represents the timeline data for a League of Legends match."""
    
    # Match reference
    match_id = Column(String(100), ForeignKey('match.match_id', ondelete='CASCADE'), 
                     nullable=False, index=True, unique=True)
    
    # Timeline metadata
    frame_interval = Column(Integer, nullable=True)  # Milliseconds between frames
    frames_processed = Column(Boolean, default=False, nullable=False)
    
    # Raw timeline data (stored as JSON for flexibility)
    timeline_data = Column(JSON, nullable=True)
    
    # Processed data (for easier querying)
    participant_frames = Column(JSON, nullable=True)  # Processed participant frames
    events = Column(JSON, nullable=True)              # Processed events
    
    # Relationships
    match = relationship("Match", back_populates="timeline", uselist=False)
    
    def __repr__(self):
        return f"<MatchTimeline(match_id={self.match_id}, frames_processed={self.frames_processed})>"
    
    @classmethod
    def create_or_update_from_api(cls, session, match_id: str, timeline_data: dict):
        """Create or update a match timeline from Riot API data."""
        timeline = session.query(cls).filter_by(match_id=match_id).first()
        
        if not timeline:
            timeline = cls(match_id=match_id)
            
        timeline.frame_interval = timeline_data.get('frameInterval', 60000)  # Default 1 minute
        timeline.timeline_data = timeline_data
        
        # Process frames and events if not already done
        if not timeline.frames_processed:
            timeline._process_timeline_data()
        
        session.add(timeline)
        return timeline
    
    def _process_timeline_data(self):
        """Process the raw timeline data into more queryable formats."""
        if not self.timeline_data or 'frames' not in self.timeline_data:
            return
            
        frames = self.timeline_data['frames']
        
        # Process participant frames
        self.participant_frames = {}
        for frame in frames:
            timestamp = frame.get('timestamp', 0)
            self.participant_frames[timestamp] = frame.get('participantFrames', {})
        
        # Process events
        self.events = []
        for frame in frames:
            if 'events' in frame:
                for event in frame['events']:
                    event_data = {
                        'timestamp': frame.get('timestamp', 0),
                        'event': event
                    }
                    self.events.append(event_data)
        
        self.frames_processed = True
        
    def get_participant_positions(self, participant_id: int) -> list:
        """Get position history for a specific participant."""
        if not self.participant_frames:
            return []
            
        positions = []
        for timestamp, frames in sorted(self.participant_frames.items()):
            participant_frame = frames.get(str(participant_id))
            if participant_frame and 'position' in participant_frame:
                positions.append({
                    'timestamp': timestamp,
                    'x': participant_frame['position']['x'],
                    'y': participant_frame['position']['y']
                })
        return positions
    
    def get_events_by_type(self, event_type: str) -> list:
        """Get all events of a specific type."""
        if not self.events:
            return []
            
        return [e for e in self.events if e.get('event', {}).get('type') == event_type]
    
    def get_kill_events(self) -> list:
        """Get all champion kill events."""
        return self.get_events_by_type('CHAMPION_KILL')
    
    def get_objective_events(self) -> list:
        """Get all objective-related events (turrets, dragons, barons, etc.)."""
        objective_types = [
            'BUILDING_KILL',  # Turrets, inhibitors
            'ELITE_MONSTER_KILL',  # Dragons, Rift Herald, Baron
            'OBJECTIVE_BOUNTY_PRESTART',
            'OBJECTIVE_BOUNTY_FINISH'
        ]
        
        if not self.events:
            return []
            
        return [e for e in self.events 
                if e.get('event', {}).get('type') in objective_types]
    
    def get_item_events(self) -> list:
        """Get all item purchase/sell events."""
        item_events = [
            'ITEM_PURCHASED',
            'ITEM_SOLD',
            'ITEM_DESTROYED',
            'ITEM_UNDO'
        ]
        
        if not self.events:
            return []
            
        return [e for e in self.events 
                if e.get('event', {}).get('type') in item_events]
    
    def get_ward_events(self) -> list:
        """Get all ward placement/kill events."""
        ward_events = [
            'WARD_PLACED',
            'WARD_KILL'
        ]
        
        if not self.events:
            return []
            
        return [e for e in self.events 
                if e.get('event', {}).get('type') in ward_events]
