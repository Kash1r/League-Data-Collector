"""Utilities for exporting match data focused on gold leads and objectives."""
import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload

from ..models import Match, Team, MatchTimeline

def get_objective_events(timeline: MatchTimeline) -> List[Dict[str, Any]]:
    """
    Extract and format objective events from match timeline.
    Only includes gold, legendary monsters, and building kills.
    """
    if not timeline or not timeline.events:
        return []
    
    objectives = []
    
    for event in timeline.events:
        event_data = event.get('event', {})
        event_type = event_data.get('type')
        timestamp = event_data.get('timestamp', 0)
        
        # Skip events that aren't related to objectives or gold
        if event_type not in ['ELITE_MONSTER_KILL', 'BUILDING_KILL', 'DRAGON_SOUL_GIVEN']:
            continue
            
        obj = {
            'timestamp': timestamp,
            'minute': timestamp // 60000 if timestamp else 0,
            'type': event_type,
            'team_id': None,
            'killer_id': None,
            'monster_type': None,
            'building_type': None,
            'lane_type': None,
            'tower_type': None,
            'bounty': 0
        }
        
        # Handle different objective types
        if event_type == 'ELITE_MONSTER_KILL':
            monster_type = event_data.get('monsterType')
            monster_sub_type = event_data.get('monsterSubType')
            
            # Only include epic monsters (dragons, baron, herald, etc.)
            if monster_type in ['DRAGON', 'RIFTHERALD', 'BARON_NASHOR'] or \
               monster_sub_type in ['FIRE_DRAGON', 'WATER_DRAGON', 'EARTH_DRAGON', 'AIR_DRAGON', 'ELDER_DRAGON']:
                obj.update({
                    'monster_type': monster_type,
                    'monster_sub_type': monster_sub_type,
                    'team_id': event_data.get('killerTeamId'),
                    'killer_id': event_data.get('killerId'),
                    'bounty': event_data.get('bounty', 0)
                })
            else:
                continue  # Skip non-epic monsters
                
        elif event_type == 'BUILDING_KILL':
            building_type = event_data.get('buildingType')
            tower_type = event_data.get('towerType')
            
            # Only include turrets, inhibitors, and the nexus
            if building_type in ['TOWER_BUILDING', 'INHIBITOR_BUILDING', 'NEXUS']:
                obj.update({
                    'building_type': building_type,
                    'lane_type': event_data.get('laneType'),
                    'tower_type': tower_type,
                    'team_id': event_data.get('killerTeamId'),  # Team that destroyed the building
                    'building_team_id': event_data.get('teamId'),  # Team that owned the building
                    'killer_id': event_data.get('killerId'),
                    'bounty': event_data.get('bounty', 0)
                })
            else:
                continue  # Skip other building types
        
        objectives.append(obj)
    
    return objectives

def export_objectives_and_gold(
    session: Session, 
    output_dir: str = 'objective_exports',
    summoner_name: Optional[str] = None
) -> Dict[str, str]:
    """
    Export match data focused on gold leads and objectives to CSV files.
    
    Args:
        session: SQLAlchemy session
        output_dir: Directory to save the CSV files
        summoner_name: Optional summoner name to filter matches
        
    Returns:
        Dict[str, str]: Dictionary mapping match IDs to file paths or error messages
    """
    from .export_utils import get_gold_leads_at_intervals
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Build base query
    query = session.query(Match).options(
        joinedload(Match.teams),
        joinedload(Match.timeline)
    )
    
    if summoner_name:
        # Debug: Log the summoner name we're searching for
        print(f"Searching for summoner name: '{summoner_name}'")
        
        # First, find the summoner in the database
        from ..models import Summoner
        summoner = session.query(Summoner).filter(Summoner.name.ilike(f"%{summoner_name}%")).first()
        
        if summoner:
            print(f"Found summoner in database: {summoner.name} (PUUID: {summoner.puuid})")
            # Get matches where this summoner participated
            query = query.join(Match.participants).filter(
                Match.participants.any(summoner_puuid=summoner.puuid)
            )
        else:
            print(f"No summoner found with name containing '{summoner_name}'. Trying partial match...")
            # Fall back to partial name match
            query = query.join(Match.participants).filter(
                Match.participants.any(summoner_name.ilike(f"%{summoner_name}%"))
            )
    
    # Debug: Print the generated SQL query
    print(f"Generated SQL query: {str(query)}\n")
    
    matches = query.all()
    print(f"Found {len(matches)} matches in the query")
    
    # Debug: Print match IDs and participants for the first few matches
    for i, match in enumerate(matches[:3]):  # Show first 3 matches for debugging
        print(f"\nMatch {i+1}:")
        print(f"  Match ID: {match.match_id}")
        print(f"  Participants ({len(match.participants)}):")
        for p in match.participants[:3]:  # Show first 3 participants
            # Print all available attributes of the participant
            print(f"    Participant ID: {p.participant_id}")
            print(f"    Summoner Name: {getattr(p, 'summoner_name', 'N/A')}")
            print(f"    Summoner PUUID: {getattr(p, 'summoner_puuid', 'N/A')}")
            print(f"    Available attributes: {[a for a in dir(p) if not a.startswith('_') and not callable(getattr(p, a))]}")
            print("    ---")
        if len(match.participants) > 3:
            print(f"    - ... and {len(match.participants) - 3} more")
    
    results = {}
    
    for match in matches:
        try:
            # Skip if no timeline data
            if not match.timeline or not match.timeline.timeline_data:
                results[match.match_id] = "No timeline data available"
                continue
            
            # Get gold leads at 1-minute intervals
            gold_leads = get_gold_leads_at_intervals(match.timeline, interval=1, max_minutes=30)
            
            # Get objective events
            objectives = get_objective_events(match.timeline)
            
            # Prepare CSV data with simplified filename
            filename = f"objectives_{match.match_id}.csv"
            filepath = os.path.join(output_dir, filename)
            
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Get winning and surrendering teams
                winning_team = None
                surrendering_team = None
                
                for team in match.teams:
                    if team.win:
                        winning_team = team.team_id
                    # Check if the team surrendered (losing team with game_ended_in_surrender flag)
                    if not team.win and hasattr(team, 'game_ended_in_surrender') and team.game_ended_in_surrender:
                        surrendering_team = team.team_id
                
                # Write match header
                writer.writerow(["Match ID:", match.match_id])
                writer.writerow(["Game Duration:", match.game_duration])
                writer.writerow(["Queue:", match.queue_id])
                writer.writerow(["Game Mode:", match.game_mode])
                writer.writerow(["Winner:", f"Team {winning_team}" if winning_team else "Unknown"])
                writer.writerow(["Surrendered:", f"Yes (Team {surrendering_team})" if surrendering_team else "No"])
                writer.writerow([""])
                
                # Write gold summary with minute-by-minute values
                writer.writerow(["Gold Summary (Minute-by-Minute)"])
                writer.writerow(["Minute", "Team 100 Gold", "Team 200 Gold", "Gold Diff (100-200)"])
                
                # Show gold for every minute
                for minute in sorted(gold_leads.keys()):
                    team_100 = gold_leads[minute][100]
                    team_200 = gold_leads[minute][200]
                    writer.writerow([
                        minute,
                        f"{team_100['gold']:,}",
                        f"{team_200['gold']:,}",
                        f"{team_100['lead']:+,}"
                    ])
                
                writer.writerow([""])
                
                # Write objectives in a cleaner format
                writer.writerow(["Objective Timeline"])
                writer.writerow(["Time", "Team", "Objective", "Details"])
                
                for obj in sorted(objectives, key=lambda x: x['timestamp']):
                    time_str = f"{obj['minute']}:{int((obj['timestamp'] % 60000) / 1000):02d}"
                    team = f"Team {obj['team_id']}" if obj['team_id'] else "Neutral"
                    
                    # Format objective description
                    if obj['type'] == 'ELITE_MONSTER_KILL':
                        monster = obj.get('monster_sub_type', obj.get('monster_type', 'Monster'))
                        objective = str(monster).replace('_', ' ').title() if monster else 'Monster'
                        details = f"{obj.get('bounty', 0)} gold" if obj.get('bounty') else ""
                    elif obj['type'] == 'BUILDING_KILL':
                        # Get the team that destroyed the building and the team that lost it
                        killer_team = obj.get('team_id')
                        lost_team = obj.get('building_team_id')
                        
                        # Format team information for display
                        team_info = []
                        if killer_team in [100, 200]:
                            team_info.append(f"Destroyed by Team {killer_team}")
                        if lost_team in [100, 200]:
                            team_info.append(f"Team {lost_team}'s building")
                        
                        # Format the building name
                        if obj.get('building_type') == 'TOWER_BUILDING':
                            tower = str(obj.get('tower_type', 'Tower')).replace('_', ' ').title()
                            lane = str(obj.get('lane_type', '')).replace('_', ' ').title()
                            objective = f"{lane} {tower}" if lane else tower
                        else:
                            building = str(obj.get('building_type', 'Building')).replace('_', ' ').title()
                            lane_str = str(obj.get('lane_type', '')).replace('_', ' ').title()
                            lane = f" ({lane_str})" if lane_str else ""
                            objective = f"{building}{lane}"
                        
                        # Add bounty information if available
                        details_parts = []
                        if team_info:
                            details_parts.append(", ".join(team_info))
                        bounty = obj.get('bounty', 0)
                        if bounty:
                            details_parts.append(f"{bounty} gold")
                        details = "; ".join(details_parts) if details_parts else ""
                    else:
                        objective = str(obj['type']).replace('_', ' ').title()
                        details = ""
                    
                    writer.writerow([time_str, team, objective, details])
            
            results[match.match_id] = filepath
            
        except Exception as e:
            results[match.match_id] = f"Error: {str(e)}"
            import traceback
            print(f"Error processing match {match.match_id}: {str(e)}")
            traceback.print_exc()
    
    # Add debug logging
    print(f"Processed {len(matches)} matches. Results: {results}")
    return results
    return results
