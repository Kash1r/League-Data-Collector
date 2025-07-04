"""Utilities for analyzing match timeline data."""
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from collections import defaultdict


def get_objective_participation(timeline_data: dict, participant_id: int) -> dict:
    """
    Analyze objective participation for a specific participant in a match.
    
    Args:
        timeline_data: The raw timeline data from Riot API
        participant_id: The participant ID to analyze (1-10)
        
    Returns:
        dict: Dictionary containing objective participation stats
    """
    if not timeline_data:
        return {}
        
    # Handle both formats: with and without 'info' key
    if 'info' in timeline_data:
        frames = timeline_data.get('info', {}).get('frames', [])
    else:
        # Handle direct format where frames are at the top level
        frames = timeline_data.get('frames', [])
    if not frames:
        return {}
    
    # Initialize objective tracking
    objectives = {
        'dragon': {'kills': 0, 'assists': 0, 'damage': 0, 'first_blood': False},
        'baron': {'kills': 0, 'assists': 0, 'damage': 0, 'first_blood': False},
        'rift_herald': {'kills': 0, 'assists': 0, 'damage': 0, 'first_blood': False},
        'turrets': {'kills': 0, 'assists': 0, 'damage': 0},
        'inhibitors': {'kills': 0, 'assists': 0, 'damage': 0},
        'objectives_contested': 0,
        'objectives_secured': 0,
    }
    
    # Track first blood for each monster type
    first_blood = {
        'dragon': False,
        'baron': False,
        'rift_herald': False,
    }
    
    # Monster type mapping from monster names
    monster_types = {
        'DRAGON': 'dragon',
        'BARON_NASHOR': 'baron',
        'RIFTHERALD': 'rift_herald',
    }
    
    # Structure to track damage to objectives
    damage_to_objectives = {}
    
    # Process each frame in the timeline
    for frame in frames:
        events = frame.get('events', [])
        for event in events:
            event_type = event.get('type', '')
            
            # Track damage to objectives
            if event_type == 'CHAMPION_KILL' and event.get('victimId', 0) >= 2400:
                # This is a monster kill, track damage
                for dmg in event.get('victimDamageReceived', []):
                    if dmg.get('participantId') == participant_id:
                        monster_name = event.get('monsterType', '').upper()
                        monster_type = monster_types.get(monster_name)
                        if monster_type:
                            if monster_type not in damage_to_objectives:
                                damage_to_objectives[monster_type] = 0
                            damage_to_objectives[monster_type] += dmg.get('damage', 0)
            
            # Track objective kills and assists
            elif event_type == 'ELITE_MONSTER_KILL':
                monster_type = event.get('monsterType', '').upper()
                monster_key = monster_types.get(monster_type)
                
                if not monster_key:
                    continue
                    
                # Check if participant got the kill or assist
                if event.get('killerId') == participant_id:
                    objectives[monster_key]['kills'] += 1
                    objectives[monster_key]['first_blood'] = not first_blood[monster_key]
                    first_blood[monster_key] = True
                    
                    # Add damage if we tracked it
                    if monster_key in damage_to_objectives:
                        objectives[monster_key]['damage'] = damage_to_objectives[monster_key]
                    
                elif participant_id in event.get('assistingParticipantIds', []):
                    objectives[monster_key]['assists'] += 1
                    
            # Track building kills and assists
            elif event_type == 'BUILDING_KILL':
                building_type = event.get('buildingType', '').lower()
                if building_type not in ['turret', 'inhibitor']:
                    continue
                    
                if event.get('killerId') == participant_id:
                    objectives[building_type + 's']['kills'] += 1
                elif participant_id in event.get('assistingParticipantIds', []):
                    objectives[building_type + 's']['assists'] += 1
    
    # Calculate participation metrics
    total_objectives = 0
    total_participation = 0
    
    for obj_type in ['dragon', 'baron', 'rift_herald']:
        obj = objectives[obj_type]
        if obj['kills'] > 0 or obj['assists'] > 0:
            total_objectives += 1
            if obj['kills'] > 0:
                total_participation += 1
                objectives['objectives_secured'] += 1
            elif obj['assists'] > 0:
                total_participation += 0.5  # Partial credit for assists
    
    # Calculate objective participation percentage
    if total_objectives > 0:
        objectives['objectives_contested'] = min(100, int((total_participation / total_objectives) * 100))
    else:
        objectives['objectives_contested'] = 0
    
    return objectives


def analyze_timeline_stats(timeline_data: dict, participant_id: int) -> Dict[str, Any]:
    """
    Analyze gold and XP leads for a specific participant's team throughout the match.
    
    Args:
        timeline_data: The raw timeline data from Riot API
        participant_id: The participant ID to analyze (1-10)
        
    Returns:
        dict: Dictionary containing gold and XP lead statistics
    """
    if not timeline_data:
        return {}
    
    # Handle both formats: with and without 'info' key
    if 'info' in timeline_data:
        frames = timeline_data.get('info', {}).get('frames', [])
    else:
        # Handle direct format where frames are at the top level
        frames = timeline_data.get('frames', [])
    if not frames:
        return {}
    
    # Find the participant's team ID
    team_id = None
    
    for frame in frames:
        if 'participantFrames' in frame:
            for pid, pdata in frame['participantFrames'].items():
                if int(pid) == participant_id:
                    team_id = pdata.get('participantId', 0) // 100 * 100  # 100 for blue, 200 for red
                    break
            if team_id is not None:
                break
    
    if team_id is None:
        return {}
    
    # Initialize stats tracking
    stats = {
        'gold_leads': [],
        'xp_leads': [],
        'gold_lead_at_15': 0,
        'xp_lead_at_15': 0,
        'max_gold_lead': 0,
        'max_xp_lead': 0,
        'avg_gold_lead': 0,
        'avg_xp_lead': 0,
        'gold_lead_percent': 0,
        'xp_lead_percent': 0,
    }
    
    # Track totals for each team
    gold_totals = []
    xp_totals = []
    
    # Process each frame to calculate team totals
    for frame in frames:
        if 'participantFrames' not in frame:
            continue
            
        blue_gold = 0
        blue_xp = 0
        red_gold = 0
        red_xp = 0
        
        # Sum gold and XP for each team
        for pid, pdata in frame['participantFrames'].items():
            p_team = (int(pid) - 1) // 5 * 100 + 100  # Calculate team ID (100 or 200)
            if p_team == 100:  # Blue team
                blue_gold += pdata.get('totalGold', 0)
                blue_xp += pdata.get('xp', 0)
            else:  # Red team
                red_gold += pdata.get('totalGold', 0)
                red_xp += pdata.get('xp', 0)
        
        # Calculate leads (positive = blue team is ahead)
        gold_lead = blue_gold - red_gold
        xp_lead = blue_xp - red_xp
        
        # Store the leads
        timestamp = frame.get('timestamp', 0) // 1000  # Convert to seconds
        gold_totals.append((timestamp, gold_lead))
        xp_totals.append((timestamp, xp_lead))
    
    # Calculate key metrics if we have data
    if gold_totals and xp_totals:
        # Get lead at 15 minutes (or closest frame before)
        target_time = 15 * 60  # 15 minutes in seconds
        
        # Find gold lead at 15 minutes
        closest_gold = min(gold_totals, key=lambda x: abs(x[0] - target_time))
        stats['gold_lead_at_15'] = closest_gold[1] if closest_gold[0] <= target_time else 0
        
        # Find XP lead at 15 minutes
        closest_xp = min(xp_totals, key=lambda x: abs(x[0] - target_time))
        stats['xp_lead_at_15'] = closest_xp[1] if closest_xp[0] <= target_time else 0
        
        # Calculate max and average leads
        gold_leads = [g for _, g in gold_totals]
        xp_leads = [x for _, x in xp_totals]
        
        if gold_leads:
            stats['max_gold_lead'] = max(abs(g) for g in gold_leads)
            stats['avg_gold_lead'] = sum(gold_leads) / len(gold_leads)
            
            # Calculate percentage of time with gold lead
            gold_lead_time = sum(1 for g in gold_leads if g > 0)
            stats['gold_lead_percent'] = (gold_lead_time / len(gold_leads)) * 100
            
        if xp_leads:
            stats['max_xp_lead'] = max(abs(x) for x in xp_leads)
            stats['avg_xp_lead'] = sum(xp_leads) / len(xp_leads)
            
            # Calculate percentage of time with XP lead
            xp_lead_time = sum(1 for x in xp_leads if x > 0)
            stats['xp_lead_percent'] = (xp_lead_time / len(xp_leads)) * 100
    
    return stats
