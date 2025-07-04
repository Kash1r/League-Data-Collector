"""Utilities for exporting database data to various formats."""
import csv
import os
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Union, Tuple
from pathlib import Path

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, and_, func

from ..models import Summoner, Match, Participant, Team, MatchTimeline

def export_to_csv(session: Session, model_class, output_dir: str = 'exports', filename: Optional[str] = None) -> str:
    """
    Export data from a SQLAlchemy model to a CSV file.
    
    Args:
        session: SQLAlchemy session
        model_class: SQLAlchemy model class to export
        output_dir: Directory to save the CSV file
        filename: Optional custom filename (without extension)
        
    Returns:
        str: Path to the created CSV file
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Get all records from the model
    records = session.query(model_class).all()
    
    if not records:
        return f"No records found for {model_class.__name__}"
    
    # Generate filename if not provided
    if not filename:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{model_class.__name__.lower()}_export_{timestamp}.csv"
    elif not filename.endswith('.csv'):
        filename += '.csv'
    
    filepath = os.path.join(output_dir, filename)
    
    # Get column names from model
    columns = [column.name for column in model_class.__table__.columns]
    
    # Write to CSV
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        
        for record in records:
            # Convert SQLAlchemy model to dict and handle JSON fields
            row = {}
            for column in columns:
                value = getattr(record, column)
                # Convert datetime to string if needed
                if hasattr(value, 'isoformat'):
                    value = value.isoformat()
                # Handle JSON fields
                elif column in ['bans', 'perks', 'challenges'] and value is not None:
                    value = str(value)  # Convert JSON to string
                row[column] = value
            writer.writerow(row)
    
    return filepath

def export_all_tables(session: Session, output_dir: str = 'exports') -> Dict[str, str]:
    """
    Export all database tables to separate CSV files.
    
    Args:
        session: SQLAlchemy session
        output_dir: Directory to save the CSV files
        
    Returns:
        Dict[str, str]: Dictionary mapping table names to file paths
    """
    models = [Summoner, Match, Participant, Team, MatchTimeline]
    results = {}
    
    for model in models:
        try:
            filepath = export_to_csv(session, model, output_dir)
            results[model.__name__] = filepath
        except Exception as e:
            results[model.__name__] = f"Error exporting {model.__name__}: {str(e)}"
    
    return results

def _safe_filename(name: str) -> str:
    """Convert a string to a safe filename."""
    # Remove invalid characters
    name = re.sub(r'[^\w\s-]', '', name.lower())
    # Replace spaces with underscores
    name = re.sub(r'[\s]+', '_', name)
    return name.strip('_')

def _format_column_name(prefix: str, name: str) -> str:
    """Format column names to be more readable."""
    # Remove common prefixes
    name = name.replace('participant_', '').replace('team_', '').replace('match_', '')
    # Convert snake_case to Title Case
    return f"{prefix}_{' '.join(word.capitalize() for word in name.split('_'))}"

def _get_team_info(teams: List[Dict], team_id: int, is_team: bool = True) -> Dict:
    """Get team information and format it for display."""
    team = next((t for t in teams if t['team_id'] == team_id), {})
    if not team:
        return {}
    
    # Format team-specific data
    team_info = {
        'team_id': team['team_id'],
        'win': 'Win' if team.get('win') else 'Loss',
        'first_blood': 'Yes' if team.get('first_blood') else 'No',
        'first_tower': 'Yes' if team.get('first_tower') else 'No',
        'tower_kills': team.get('tower_kills', 0),
        'inhibitor_kills': team.get('inhibitor_kills', 0),
        'baron_kills': team.get('baron_kills', 0),
        'dragon_kills': team.get('dragon_kills', 0),
        'rift_herald_kills': team.get('rift_herald_kills', 0)
    }
    
    return team_info

# Item ID to name mapping (common items)
# Source: https://leagueoflegends.fandom.com/wiki/Item_(League_of_Legends)
ITEM_NAMES = {
    # Starter Items
    1054: "Doran's Ring",
    1055: "Doran's Blade",
    1056: "Doran's Shield",
    1082: "Dark Seal",
    1083: "Cull",
    
    # Boots
    1001: "Boots of Speed",
    3006: "Berserker's Greaves",
    3009: "Boots of Swiftness",
    3020: "Sorcerer's Shoes",
    3047: "Plated Steelcaps",
    3111: "Mercury's Treads",
    3117: "Mobility Boots",
    3158: "Ionian Boots of Lucidity",
    
    # Mythic Items
    2065: "Shurelya's Battlesong",
    3078: "Trinity Force",
    3089: "Rabadon's Deathcap",
    3152: "Hextech Rocketbelt",
    3190: "Locket of the Iron Solari",
    4005: "Imperial Mandate",
    4637: "Watchful Wardstone",
    4645: "Vigilant Wardstone",
    6653: "Riftmaker",
    6655: "Luden's Tempest",
    6656: "Liandry's Anguish",
    6662: "Iceborn Gauntlet",
    6664: "Turbo Chemtank",
    6671: "Galeforce",
    6672: "Kraken Slayer",
    6673: "Immortal Shieldbow",
    
    # Legendary Items
    1031: "Scout's Slingshot",
    2502: "Scout's Slingshot (Upgrade)",
    3065: "Spirit Visage",
    3068: "Sunfire Aegis",
    3076: "Thornmail",
    3173: "Redemption",
    3001: "Abyssal Mask",
    3003: "Archangel's Staff",
    3004: "Manamune",
    3020: "Lich Bane",
    3031: "Infinity Edge",
    3033: "Mortal Reminder",
    3036: "Lord Dominik's Regards",
    3050: "Zeke's Convergence",
    3053: "Sterak's Gage",
    3057: "Sheen",
    3071: "Black Cleaver",
    3072: "Bloodthirster",
    3074: "Ravenous Hydra",
    3075: "Thornmail",
    3083: "Warmog's Armor",
    3085: "Runaan's Hurricane",
    3091: "Wit's End",
    3094: "Rapid Firecannon",
    3095: "Stormrazor",
    3100: "Lich Bane",
    3102: "Banshee's Veil",
    3107: "Redemption",
    3109: "Knight's Vow",
    3110: "Frozen Heart",
    3115: "Nashor's Tooth",
    3116: "Rylai's Crystal Scepter",
    3124: "Guinsoo's Rageblade",
    3135: "Void Staff",
    3139: "Mercurial Scimitar",
    3142: "Youmuu's Ghostblade",
    3143: "Randuin's Omen",
    3147: "Duskblade of Draktharr",
    3153: "Blade of the Ruined King",
    3156: "Maw of Malmortius",
    3157: "Zhonya's Hourglass",
    3165: "Morellonomicon",
    3179: "Umbral Glaive",
    3181: "Sanguine Blade",
    3191: "Seeker's Armguard",
    3193: "Gargoyle Stoneplate",
    3211: "Spectre's Cowl",
    3222: "Mikael's Blessing",
    3285: "Luden's Tempest",
    3504: "Ardent Censer",
    3508: "Essence Reaver",
    3742: "Dead Man's Plate",
    3748: "Titanic Hydra",
    3814: "Edge of Night",
    
    # Support Items
    3303: "Spellthief's Edge",
    3306: "Relic Shield",
    3850: "Spellthief's Edge",
    3851: "Frostfang",
    3853: "Shard of True Ice",
    3854: "Steel Shoulderguards",
    3855: "Runesteel Spaulders",
    3857: "Pauldrons of Whiterock",
    3858: "Relic Shield",
    3859: "Targon's Buckler",
    3860: "Bulwark of the Mountain",
    3862: "Spectral Sickle",
    3863: "Harrowing Crescent",
    3864: "Black Mist Scythe",
    
    # Trinkets
    3340: "Warding Totem",
    3348: "Arcane Sweeper",
    3363: "Farsight Alteration",
    3364: "Oracle Lens",
    3330: "Scarecrow Effigy (Fiddle Sticks)",
    
    # Consumables
    2003: "Health Potion",
    2010: "Total Biscuit of Everlasting Will",
    2031: "Refillable Potion",
    2033: "Corrupting Potion",
    2138: "Elixir of Iron",
    2139: "Elixir of Sorcery",
    2140: "Elixir of Wrath",
    
    # Special
    3400: "Your Cut",
    3504: "Ardent Censer",
    3513: "Eye of the Herald",
    3907: "Fire at Will",
    3908: "Death's Daughter",
    3916: "Raise Morale",
}

# Summoner spell ID to name mapping
SUMMONER_SPELLS = {
    1: 'Cleanse',
    3: 'Exhaust',
    4: 'Flash',
    6: 'Ghost',
    7: 'Heal',
    11: 'Smite',
    12: 'Teleport',
    13: 'Clarity',
    14: 'Ignite',
    21: 'Barrier',
    30: 'To the King!',
    31: 'Poro Toss',
    32: 'Mark',
    39: 'Mark',
}

def _get_item_names(item_ids: List[int]) -> List[str]:
    """Convert item IDs to their names with better fallback handling.
    
    Args:
        item_ids: List of item IDs to convert
        
    Returns:
        List of item names, with fallback to descriptive names for unknown items
    """
    result = []
    for item_id in item_ids:
        if item_id == 0:  # Skip empty item slots
            continue
            
        # First check if we have a direct mapping
        if item_id in ITEM_NAMES:
            result.append(ITEM_NAMES[item_id])
            continue
            
        # Handle trinkets and special items
        if item_id == 3364:  # Oracle Lens
            result.append("Oracle Lens")
            continue
            
        # Try to determine item type from ID range with better fallbacks
        if 1001 <= item_id <= 1999:  # Boots
            result.append(f"Boots (ID: {item_id})")
        elif 2000 <= item_id <= 2999:  # Consumables
            if item_id == 2055:  # Control Ward
                result.append("Control Ward")
            else:
                result.append(f"Consumable (ID: {item_id})")
        elif 3000 <= item_id <= 3999:  # Legendary items
            result.append(f"Legendary Item (ID: {item_id})")
        elif 4000 <= item_id <= 4999:  # Mythic items
            result.append(f"Mythic Item (ID: {item_id})")
        elif 5000 <= item_id <= 5999:  # Boot upgrades
            result.append(f"Boot Upgrade (ID: {item_id})")
        else:
            # For any other IDs, just show the ID
            result.append(f"Item {item_id}")
    return result

def _get_summoner_spell(spell_id: int) -> str:
    """Get summoner spell name by ID."""
    return SUMMONER_SPELLS.get(spell_id, f'Spell {spell_id}')

def _get_participant_info(participant: Dict, match_duration: int, is_main_player: bool = False) -> Dict:
    """Extract and format participant information with enhanced stats."""
    # Get basic stats with defaults
    stats = {
        'kills': participant.get('kills', 0),
        'deaths': participant.get('deaths', 0),
        'assists': participant.get('assists', 0),
        'total_minions_killed': participant.get('total_minions_killed', 0),
        'neutral_minions_killed': participant.get('neutral_minions_killed', 0),
        'gold_earned': participant.get('gold_earned', 0),
        'damage_dealt_to_champions': participant.get('damage_dealt_to_champions', 0),
        'total_damage_taken': participant.get('total_damage_taken', 0),
        'total_heal': participant.get('total_heal', 0),
        'vision_score': participant.get('vision_score', 0),
        'wards_placed': participant.get('wards_placed', 0),
        'wards_killed': participant.get('wards_killed', 0),
        'summoner1_id': participant.get('summoner1_id', 0),
        'summoner2_id': participant.get('summoner2_id', 0),
        'team_position': 'UNKNOWN',
        'champion_level': 1,
        'champion_name': 'Unknown',
        'summoner_name': 'Unknown'
    }
    
    # Update with actual values from participant
    for key in stats.keys():
        if key in participant:
            stats[key] = participant[key] if participant[key] is not None else stats[key]
    
    # Calculate derived stats
    cs = stats['total_minions_killed'] + stats['neutral_minions_killed']
    minutes = max(1, match_duration / 60)  # Avoid division by zero
    cs_per_min = round(cs / minutes, 1) if minutes > 0 else 0
    kda_ratio = (stats['kills'] + stats['assists']) / max(1, stats['deaths'])  # Avoid division by zero
    
    # Get items
    items = []
    for i in range(7):
        item_id = participant.get(f'item{i}')
        if item_id and item_id > 0:  # Only include valid item IDs
            item_name = ITEM_NAMES.get(item_id, f"Item {item_id}")
            items.append(item_name)
    
    # Get summoner spells
    spell1 = _get_summoner_spell(stats['summoner1_id'])
    spell2 = _get_summoner_spell(stats['summoner2_id'])
    
    return {
        'summoner_name': stats['summoner_name'],
        'champion_name': stats['champion_name'],
        'champion_level': stats['champion_level'],
        'kills': stats['kills'],
        'deaths': stats['deaths'],
        'assists': stats['assists'],
        'kda': kda_ratio,
        'kda_display': f"{stats['kills']}/{stats['deaths']}/{stats['assists']} ({kda_ratio:.1f})",
        'total_minions_killed': stats['total_minions_killed'],
        'neutral_minions_killed': stats['neutral_minions_killed'],
        'cs': cs,
        'cs_per_min': cs_per_min,
        'gold_earned': stats['gold_earned'],
        'damage_dealt_to_champions': stats['damage_dealt_to_champions'],
        'total_damage_taken': stats['total_damage_taken'],
        'total_heal': stats['total_heal'],
        'vision_score': stats['vision_score'],
        'wards_placed': stats['wards_placed'],
        'wards_killed': stats['wards_killed'],
        'items': items,
        'item0': participant.get('item0', 0),
        'item1': participant.get('item1', 0),
        'item2': participant.get('item2', 0),
        'item3': participant.get('item3', 0),
        'item4': participant.get('item4', 0),
        'item5': participant.get('item5', 0),
        'item6': participant.get('item6', 0),
        'summoner1_id': stats['summoner1_id'],
        'summoner2_id': stats['summoner2_id'],
        'summoner_spell1': spell1,
        'summoner_spell2': spell2,
        'summoner_spells': f"{spell1} / {spell2}",
        'is_main_player': is_main_player,
        'team_position': stats['team_position']
    }

def get_gold_lead_at_time(timeline: MatchTimeline, minutes: int) -> Optional[Dict[int, Dict[str, int]]]:
    """Calculate the gold values and lead for each team at a specific minute.
    
    Args:
        timeline: The MatchTimeline object containing the timeline data
        minutes: The minute mark to get gold data for (e.g., 5, 10, 15)
        
    Returns:
        Dict with team_id as key and dict containing gold values and lead,
        or None if data is not available
    """
    if not timeline or not timeline.participant_frames:
        return None
        
    # Convert minutes to milliseconds
    target_time = minutes * 60 * 1000
    
    # Find the frame closest to the target time
    closest_time = None
    min_diff = float('inf')
    
    for timestamp in timeline.participant_frames.keys():
        timestamp_ms = int(timestamp)
        diff = abs(timestamp_ms - target_time)
        if diff < min_diff:
            min_diff = diff
            closest_time = timestamp_ms
    
    # If the closest frame is too far from the target time, return None
    if min_diff > 90 * 1000:  # More than 1.5 minutes difference
        return None
    
    # Get the participant frames for the closest time
    frames = timeline.participant_frames.get(str(closest_time), {})
    if not frames:
        return None
    
    # Calculate total gold for each team
    team_gold = {100: 0, 200: 0}
    
    for participant_id, frame in frames.items():
        if not isinstance(participant_id, str) or not participant_id.isdigit():
            continue
            
        participant_id = int(participant_id)
        team_id = 100 if participant_id <= 5 else 200  # Participants 1-5 are team 100, 6-10 are team 200
        team_gold[team_id] += frame.get('totalGold', 0)
    
    # Calculate gold values and leads
    result = {
        100: {
            'gold': team_gold[100],
            'lead': team_gold[100] - team_gold[200],
            'timestamp': closest_time
        },
        200: {
            'gold': team_gold[200],
            'lead': team_gold[200] - team_gold[100],
            'timestamp': closest_time
        }
    }
    
    return result

def get_gold_leads_at_intervals(timeline: MatchTimeline, interval: int = 1, max_minutes: int = 30) -> Dict[int, Dict[int, Dict[str, int]]]:
    """Get gold leads at regular intervals throughout the match.
    
    Args:
        timeline: The MatchTimeline object containing the timeline data
        interval: Interval in minutes (default: 1 for minute-by-minute)
        max_minutes: Maximum match time in minutes (default: 30)
        
    Returns:
        Dict with minute marks as keys and gold data as values
    """
    gold_leads = {}
    
    # Get all available timestamps from the timeline
    if not timeline or not timeline.participant_frames:
        return {}
        
    # Get all timestamps and sort them
    all_timestamps = sorted([int(ts) for ts in timeline.participant_frames.keys()])
    if not all_timestamps:
        return {}
        
    # Convert max_minutes to milliseconds
    max_time_ms = max_minutes * 60 * 1000
    
    # For each minute, find the closest frame
    for minute in range(1, max_minutes + 1, interval):
        target_time = minute * 60 * 1000  # Convert to milliseconds
        if target_time > max_time_ms:
            continue
            
        # Find the closest timestamp to our target time
        closest_ts = min(all_timestamps, key=lambda x: abs(x - target_time))
        
        # Only use if within 30 seconds of target time
        if abs(closest_ts - target_time) <= 30000:  # 30 seconds
            # Get the data for this timestamp
            frames = timeline.participant_frames.get(str(closest_ts), {})
            if not frames:
                continue
                
            # Calculate team gold
            team_gold = {100: 0, 200: 0}
            for participant_id, frame in frames.items():
                if not isinstance(participant_id, str) or not participant_id.isdigit():
                    continue
                participant_id = int(participant_id)
                team_id = 100 if participant_id <= 5 else 200
                team_gold[team_id] += frame.get('totalGold', 0)
                
            # Store the data
            gold_leads[minute] = {
                100: {
                    'gold': team_gold[100],
                    'lead': team_gold[100] - team_gold[200],
                    'timestamp': closest_ts
                },
                200: {
                    'gold': team_gold[200],
                    'lead': team_gold[200] - team_gold[100],
                    'timestamp': closest_ts
                }
            }
    
    return gold_leads

def _get_match_info(match: Dict) -> Dict:
    """Extract and format match information."""
    from datetime import datetime
    
    game_creation = match.get('game_creation')
    if isinstance(game_creation, str):
        try:
            game_creation = datetime.fromisoformat(game_creation.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            game_creation = None
    
    return {
        'match_id': match.get('match_id', 'Unknown'),
        'game_mode': match.get('game_mode', 'Unknown'),
        'queue_id': match.get('queue_id', 0),
        'game_duration': match.get('game_duration', 0) // 60,  # Convert to minutes
        'game_version': match.get('game_version', 'Unknown'),
        'game_date': game_creation.strftime('%Y-%m-%d %H:%M') if game_creation else 'Unknown',
        'map_id': match.get('map_id', 0)
    }

def export_match_data(session: Session, output_dir: str = 'match_exports', 
                    summoner_name: Optional[str] = None) -> Dict[str, str]:
    """
    Export match data with all related information to CSV files, one file per match.
    Uses an Excel-friendly format with tabular data and consistent columns.
    
    Args:
        session: SQLAlchemy session
        output_dir: Directory to save the CSV files
        summoner_name: Optional summoner name to filter matches
        
    Returns:
        Dict[str, str]: Dictionary mapping match IDs to file paths or error messages
    """
    import logging
    from pathlib import Path
    from datetime import datetime
    import os
    
    from ..models import Match, Participant, Team, Summoner
    from sqlalchemy.orm import joinedload
    from sqlalchemy import func
    
    logger = logging.getLogger(__name__)
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Build base query with joins to load all related data efficiently
    query = session.query(Match).options(
        joinedload(Match.participants).joinedload(Participant.summoner),
        joinedload(Match.teams)
    )
    
    # Filter by summoner name if provided
    if summoner_name:
        query = query.join(Match.participants).join(Participant.summoner).filter(
            func.lower(Summoner.name).contains(func.lower(summoner_name))
        )
    
    # Execute query and get all matches
    matches = query.all()
    
    results = {}
    
    for match in matches:
        try:
            # Get all participants with their summoner info
            participants = sorted(match.participants, key=lambda p: p.participant_id)
            
            # Find the main participant if a summoner name was provided
            main_participant = None
            if summoner_name:
                main_participant = next(
                    (p for p in participants 
                     if p.summoner and p.summoner.name and 
                     summoner_name.lower() in p.summoner.name.lower()),
                    None
                )
            
            # Generate filename using match ID and date
            date_str = match.game_creation.strftime('%Y%m%d') if match.game_creation else 'unknown_date'
            # Remove any non-alphanumeric characters from match ID for filename safety
            safe_match_id = ''.join(c for c in match.match_id if c.isalnum() or c == '_')
            filename = f"match_{date_str}_{safe_match_id}.csv"
            filepath = os.path.join(output_dir, filename)
            
            # Get gold leads at 1-minute intervals
            gold_leads = {}
            if match.timeline and match.timeline.participant_frames:
                gold_leads = get_gold_leads_at_intervals(match.timeline, interval=1, max_minutes=30)
            
            # Get team information
            teams = {}
            for team in match.teams:
                team_id = team.team_id
                teams[team_id] = {
                    'info': {
                        'team_id': team_id,
                        'win': 'Win' if team.win else 'Loss',
                        'tower_kills': team.tower_kills or 0,
                        'inhibitor_kills': team.inhibitor_kills or 0,
                        'baron_kills': team.baron_kills or 0,
                        'dragon_kills': team.dragon_kills or 0,
                        'rift_herald_kills': team.rift_herald_kills or 0,
                        'gold_leads': gold_leads,
                    },
                    'participants': []
                }
            
            # Process participants
            for p in participants:
                # Get summoner name with better handling
                summoner_name = None
                if hasattr(p, 'summoner') and p.summoner and p.summoner.name:
                    summoner_name = p.summoner.name
                elif hasattr(p, 'summoner_name') and p.summoner_name:
                    summoner_name = p.summoner_name
                else:
                    # If we don't have a name, use a more descriptive placeholder
                    summoner_name = f"Player {p.participant_id} ({p.champion_name})"
                
                # Convert participant to dict with all attributes
                p_data = {c.name: getattr(p, c.name, None) for c in Participant.__table__.columns}
                p_data['summoner_name'] = summoner_name
                
                # Add champion name if missing
                if not p_data.get('champion_name') and hasattr(p, 'champion_name'):
                    p_data['champion_name'] = p.champion_name
                
                # Add to team
                is_main = (p == main_participant) if main_participant else False
                participant_info = _get_participant_info(p_data, match.game_duration if match.game_duration else 1800, is_main)
                teams[p.team_id]['participants'].append(participant_info)
            
            # Write to CSV
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Helper function to write sections
                def write_section(header, rows, add_extra_line=True):
                    writer.writerow([header])
                    for row in rows:
                        writer.writerow(row)
                    if add_extra_line:
                        writer.writerow([])
                
                # Match Info
                match_info = [
                    ['Match ID', match.match_id],
                    ['Game Mode', match.game_mode or 'Unknown'],
                    ['Queue', str(match.queue_id) if match.queue_id else 'Unknown'],
                    ['Date', match.game_creation.strftime('%Y-%m-%d %H:%M') if match.game_creation else 'Unknown'],
                    ['Duration', f"{int(match.game_duration // 60)}m {int(match.game_duration % 60)}s" if match.game_duration else 'Unknown'],
                    ['Version', match.game_version or 'Unknown']
                ]
                
                # Add gold leads at minute intervals if available
                if gold_leads:
                    # Add a section header
                    match_info.append(['', ''])
                    match_info.append(['GOLD LEAD PER MINUTE', ''])
                    
                    # Group by team for easier display
                    team_100_gold = []
                    team_200_gold = []
                    
                    for minute, leads in sorted(gold_leads.items()):
                        team_100 = leads[100]
                        team_200 = leads[200]
                        
                        # Add to team-specific lists
                        team_100_gold.append(f"{minute}: {team_100['gold']:,}g ({team_100['lead']:+,}g)")
                        team_200_gold.append(f"{minute}: {team_200['gold']:,}g ({team_200['lead']:+,}g)")
                    
                    # Add team gold progress to match info - split into multiple lines if needed
                    max_line_length = 100
                    team_100_chunks = []
                    current_chunk = []
                    current_length = 0
                    
                    for entry in team_100_gold:
                        if current_length + len(entry) + 2 > max_line_length and current_chunk:
                            team_100_chunks.append(' | '.join(current_chunk))
                            current_chunk = []
                            current_length = 0
                        current_chunk.append(entry)
                        current_length += len(entry) + 2  # +2 for ' | ' separator
                    
                    if current_chunk:
                        team_100_chunks.append(' | '.join(current_chunk))
                    
                    # Add team 100 gold data
                    for i, chunk in enumerate(team_100_chunks):
                        if i == 0:
                            match_info.append(['Team 100 Gold', chunk])
                        else:
                            match_info.append(['', chunk])
                    
                    # Same for team 200
                    team_200_chunks = []
                    current_chunk = []
                    current_length = 0
                    
                    for entry in team_200_gold:
                        if current_length + len(entry) + 2 > max_line_length and current_chunk:
                            team_200_chunks.append(' | '.join(current_chunk))
                            current_chunk = []
                            current_length = 0
                        current_chunk.append(entry)
                        current_length += len(entry) + 2  # +2 for ' | ' separator
                    
                    if current_chunk:
                        team_200_chunks.append(' | '.join(current_chunk))
                    
                    # Add team 200 gold data
                    for i, chunk in enumerate(team_200_chunks):
                        if i == 0:
                            match_info.append(['Team 200 Gold', chunk])
                        else:
                            match_info.append(['', chunk])
                    
                    # Add a summary of key moments
                    match_info.append(['', ''])
                    match_info.append(['GOLD LEAD SUMMARY', ''])
                    
                    # Find the minute where the lead changed the most
                    max_swing = 0
                    max_swing_minute = 0
                    prev_lead = 0
                    
                    for minute, leads in sorted(gold_leads.items()):
                        if minute == 1:
                            prev_lead = leads[100]['lead']
                            continue
                            
                        current_lead = leads[100]['lead']
                        swing = abs(current_lead - prev_lead)
                        
                        if swing > max_swing:
                            max_swing = swing
                            max_swing_minute = minute
                            
                        prev_lead = current_lead
                    
                    if max_swing_minute > 0:
                        leads = gold_leads[max_swing_minute]
                        winning_team = 100 if leads[100]['lead'] > 0 else 200
                        match_info.append([
                            f'Biggest Lead Change @{max_swing_minute}min',
                            f"Team {winning_team} gained {max_swing:,}g advantage"
                        ])
                    
                    # Add final gold difference
                    if gold_leads:
                        last_minute = max(gold_leads.keys())
                        final_leads = gold_leads[last_minute]
                        winning_team = 100 if final_leads[100]['lead'] > 0 else 200
                        match_info.append([
                            'Final Gold Difference',
                            f"Team {winning_team} ahead by {abs(final_leads[winning_team]['lead']):,}g"
                        ])
                write_section('MATCH INFORMATION', match_info)
                
                # Teams and Participants
                for team_id, team_data in teams.items():
                    team_info = team_data['info']
                    # Add gold leads to team header if available
                    gold_leads_str = ""
                    if team_info.get('gold_leads'):
                        # Find the latest minute with data
                        if team_info['gold_leads']:
                            latest_minute = max(team_info['gold_leads'].keys())
                            lead = team_info['gold_leads'][latest_minute][team_id]['lead']
                            gold_leads_str = f" | Gold @{latest_minute}: {lead:+,}g"
                        
                    team_header = (
                        f"TEAM {team_id} ({team_info['win']}): "
                        f"Towers: {team_info['tower_kills']} | "
                        f"Dragons: {team_info['dragon_kills']} | "
                        f"Barons: {team_info['baron_kills']} | "
                        f"Heralds: {team_info['rift_herald_kills']}"
                        f"{gold_leads_str}"
                    )
                    
                    writer.writerow([team_header])
                    writer.writerow([])  # Empty line after team header
                    
                    # Process each participant
                    for p in team_data['participants']:
                        summoner_name = f"★ {p['summoner_name']}" if p.get('is_main_player') else p['summoner_name']
                        
                        # Basic info
                        participant_rows = [
                            ['Summoner', summoner_name],
                            ['Champion', p['champion_name']],
                            ['Role', p['team_position']],
                            ['Level', p['champion_level']],
                            ['KDA', p['kda_display']],
                            ['CS', f"{p['cs']} ({p['cs_per_min']:.1f}/min)"],
                            ['Gold', f"{p['gold_earned']:,}"],
                            ['Damage to Champs', f"{p['damage_dealt_to_champions']:,}"],
                            ['Damage Taken', f"{p['total_damage_taken']:,}"],
                            ['Healing', f"{p['total_heal']:,}"],
                            ['Vision Score', p['vision_score']],
                            ['Wards Placed/Killed', f"{p['wards_placed']}/{p['wards_killed']}"],
                            ['Summoner Spells', p['summoner_spells']],
                            ['Items', ', '.join(p['items']) if p['items'] else 'None']
                        ]
                        
                        write_section(f"PARTICIPANT: {summoner_name}", participant_rows)
                    
                    # Add space between teams
                    if team_id != list(teams.keys())[-1]:
                        writer.writerow([])
                
                # Match Summary
                match_summary = [
                    ['Match ID', match.match_id],
                    ['Duration', f"{int(match.game_duration // 60)}m {int(match.game_duration % 60)}s" if match.game_duration else 'Unknown'],
                    ['Game Mode', match.game_mode or 'Unknown'],
                    ['Queue', str(match.queue_id) if match.queue_id else 'Unknown'],
                    ['Version', match.game_version or 'Unknown']
                ]
                write_section('MATCH SUMMARY', match_summary, add_extra_line=False)
            
            results[match.match_id] = filepath
            
        except Exception as e:
            match_id = getattr(match, 'match_id', 'unknown')
            logger.exception(f"Error exporting match {match_id}")
            results[match_id] = f"Error exporting match {match_id}: {str(e)}"
    
    return results
