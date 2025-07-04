"""Data cleaning and transformation utilities for Riot API data."""
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

from sqlalchemy.orm import Session

from ..models import (
    Summoner, Match, Participant, Team,
    SessionLocal, get_db_session
)
from ..riot_api import RiotAPIClient

logger = logging.getLogger(__name__)

def process_summoner_data(
    api_client: RiotAPIClient,
    summoner_name: str,
    region: str = 'na1',
    session: Optional[Session] = None
) -> Tuple[Optional[Summoner], bool]:
    """
    Process summoner data from the Riot API.
    
    Args:
        api_client: Initialized RiotAPIClient
        summoner_name: Summoner name to look up
        region: Region code (default: 'na1')
        session: Optional database session (will create one if not provided)
        
    Returns:
        Tuple of (summoner, is_new) where is_new indicates if the summoner was just created
    """
    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True
    
    try:
        # Check if summoner already exists in the database by name and region
        existing_summoner = None
        
        # If using Riot ID format, try to find by name part first
        if '#' in summoner_name:
            game_name = summoner_name.split('#')[0]
            existing_summoner = session.query(Summoner).filter(
                Summoner.name == game_name,
                Summoner.region == region.lower()
            ).first()
        
        # If not found or not using Riot ID format, try exact match
        if not existing_summoner:
            existing_summoner = session.query(Summoner).filter(
                Summoner.name == summoner_name,
                Summoner.region == region.lower()
            ).first()
        
        # Only fetch from API if we don't have the summoner or it's been a while
        if existing_summoner:
            logger.info(f"Found existing summoner in database: {summoner_name}")
            return existing_summoner, False
        
        # Handle Riot ID format (name#tag)
        if '#' in summoner_name:
            game_name, tag_line = summoner_name.split('#', 1)
            logger.info(f"Processing Riot ID: {game_name}#{tag_line}")
            
            try:
                # First get account info to get PUUID
                logger.info(f"Fetching account data for {game_name}#{tag_line}")
                account_data = api_client.get_account_by_riot_id(game_name, tag_line)
                
                if not account_data or 'puuid' not in account_data:
                    logger.error(f"Failed to fetch account data for {game_name}#{tag_line}")
                    return None, False
                
                # Now get summoner data using PUUID
                logger.info(f"Fetching summoner data for PUUID: {account_data['puuid']}")
                summoner_data = api_client.get_summoner_by_puuid(account_data['puuid'])
                
                if not summoner_data:
                    logger.error(f"Failed to fetch summoner data for PUUID: {account_data['puuid']}")
                    return None, False
                
                # Combine account and summoner data
                full_data = {
                    **account_data,
                    **summoner_data,
                    'name': game_name  # Use the name from Riot ID
                }
                
                # Create or update summoner in database
                summoner = Summoner.create_or_update_from_api(session, full_data, region)
                session.commit()
                
                logger.info(f"Processed summoner: {summoner.name} (PUUID: {summoner.puuid})")
                return summoner, True
                
            except Exception as e:
                logger.error(f"Error processing Riot ID {game_name}#{tag_line}: {str(e)}", exc_info=True)
                return None, False
        else:
            # Fallback for direct summoner name (may not work with all APIs)
            logger.warning("Direct summoner name lookup may not work. Please use Riot ID format (name#tag).")
            try:
                # Try to get summoner by name (if this endpoint is available)
                summoner_data = {
                    'name': summoner_name,
                    'puuid': f'temp_{summoner_name.lower().replace(" ", "_")}',
                    'summonerLevel': 0
                }
                
                summoner = Summoner.create_or_update_from_api(session, summoner_data, region)
                session.commit()
                
                logger.warning(f"Created placeholder summoner. Please use Riot ID (name#tag) for full functionality.")
                logger.info(f"Processed summoner: {summoner.name} (PUUID: {summoner.puuid})")
                return summoner, True
                
            except Exception as e:
                logger.error(f"Error processing summoner {summoner_name}: {str(e)}", exc_info=True)
                return None, False
        
    except Exception as e:
        logger.error(f"Error processing summoner data: {str(e)}", exc_info=True)
        if close_session and session:
            session.rollback()
        raise
    finally:
        if close_session and session:
            session.close()

def process_match_data(
    api_client: RiotAPIClient,
    match_id: str,
    region: str = 'americas',
    session: Optional[Session] = None,
    include_timeline: bool = True,
    target_puuid: Optional[str] = None,
    only_requested_user: bool = True
) -> Tuple[Optional[Match], bool]:
    """
    Process match data from the Riot API.
    
    Args:
        api_client: Initialized RiotAPIClient
        match_id: Match ID to process
        region: Regional routing value (default: 'americas')
        session: Optional database session
        include_timeline: Whether to fetch and process timeline data (default: True)
        target_puuid: If provided, only store data for this specific user when only_requested_user is True
        only_requested_user: If True, only store data for the target_puuid user (default: True)
        
    Returns:
        Tuple of (match, is_new) where is_new indicates if the match was just created
    """
    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True
    
    try:
        # Fetch match data from Riot API
        match_data = api_client.get_match_details(match_id, region)
        if not match_data:
            return None, False
        
        # Determine if we should process all participants or just the target user
        process_all_participants = not only_requested_user
        
        # Process the match data
        match, is_new = _process_match_data(
            session, 
            match_data, 
            target_puuid if only_requested_user else None
        )
        
        # Process timeline data if requested
        if include_timeline and (process_all_participants or 
                               any(p['puuid'] == target_puuid for p in match_data['info'].get('participants', []))):
            try:
                timeline_data = api_client.get_match_timeline(match_id, region)
                if timeline_data and 'info' in timeline_data:
                    from ..models.match_timeline import MatchTimeline
                    MatchTimeline.create_or_update_from_api(session, match_id, timeline_data['info'])
                    session.commit()
                    logger.info(f"Processed timeline data for match {match_id}")
            except Exception as e:
                logger.error(f"Error processing timeline for match {match_id}: {str(e)}", exc_info=True)
                # Don't fail the entire process if timeline fails
                session.rollback()
        
        return match, is_new
        
    except Exception as e:
        logger.error(f"Error processing match {match_id}: {str(e)}", exc_info=True)
        if close_session and session:
            session.rollback()
        raise
    finally:
        if close_session and session:
            session.close()

def _process_match_data(session: Session, match_data: Dict[str, Any], target_puuid: Optional[str] = None) -> Tuple[Match, bool]:
    """
    Process match data and store it in the database.
    
    Args:
        session: Database session
        match_data: Raw match data from Riot API
        target_puuid: If provided and only_requested_user is True, only store data for this specific user
        
    Returns:
        Tuple of (match, is_new)
    """
    # Create or update match and commit it first to satisfy foreign key constraints
    match = Match.create_or_update_from_api(session, match_data)
    session.commit()  # Commit match first to get an ID
    
    # Process teams
    teams_data = {}
    for team_data in match_data['info'].get('teams', []):
        team = Team(
            match_id=match.match_id,
            team_id=team_data['teamId'],
            win=team_data.get('win', False),
            first_blood=team_data.get('objectives', {}).get('champion', {}).get('first', False),
            first_tower=team_data.get('objectives', {}).get('tower', {}).get('first', False),
            first_inhibitor=team_data.get('objectives', {}).get('inhibitor', {}).get('first', False),
            first_baron=team_data.get('objectives', {}).get('baron', {}).get('first', False),
            first_dragon=team_data.get('objectives', {}).get('dragon', {}).get('first', False),
            first_rift_herald=team_data.get('objectives', {}).get('riftHerald', {}).get('first', False),
            tower_kills=team_data.get('objectives', {}).get('tower', {}).get('kills', 0),
            inhibitor_kills=team_data.get('objectives', {}).get('inhibitor', {}).get('kills', 0),
            baron_kills=team_data.get('objectives', {}).get('baron', {}).get('kills', 0),
            dragon_kills=team_data.get('objectives', {}).get('dragon', {}).get('kills', 0),
            rift_herald_kills=team_data.get('objectives', {}).get('riftHerald', {}).get('kills', 0),
            bans=team_data.get('bans', [])
        )
        # Check if team already exists to avoid duplicates
        existing_team = session.query(Team).filter(
            Team.match_id == match.match_id,
            Team.team_id == team.team_id
        ).first()
        
        if not existing_team:
            session.add(team)
            teams_data[team.team_id] = team
    
    # Commit teams before adding participants
    session.commit()
    
    # Process participants - only include target user if specified
    participants_data = match_data['info'].get('participants', [])
    
    # If target_puuid is provided, filter to only include that participant
    if target_puuid:
        participants_data = [p for p in participants_data if p.get('puuid') == target_puuid]
        if not participants_data:
            logger.warning(f"Target PUUID {target_puuid} not found in match {match_data['metadata'].get('matchId')}")
    
    for idx, participant_data in enumerate(participants_data):
        participant_id = participant_data.get('participantId', idx + 1)
        puuid = participant_data.get('puuid')
        
        # Try to find existing summoner by PUUID or create a new one if not found
        summoner = None
        if puuid:
            summoner = session.query(Summoner).filter(Summoner.puuid == puuid).first()
            if not summoner:
                # Get summoner name or generate a placeholder if not available
                summoner_name = participant_data.get('summonerName', '')
                if not summoner_name.strip():
                    # If no name is provided, create a placeholder using first 8 chars of PUUID
                    summoner_name = f'Player_{puuid[:8]}'
                
                # Create a basic summoner record if it doesn't exist
                summoner = Summoner(
                    puuid=puuid,
                    name=summoner_name,
                    summoner_level=participant_data.get('summonerLevel', 1),
                    profile_icon_id=participant_data.get('profileIcon', 0),
                    region=match_data['info'].get('platformId', '').lower() or 'na1',  # Default to 'na1' if not specified
                    account_id=participant_data.get('accountId', ''),  # This field is deprecated but required
                    summoner_id=participant_data.get('summonerId', '')  # This field is deprecated but required
                )
                
                # Check if a summoner with the same name and region already exists
                existing_summoner = session.query(Summoner).filter(
                    Summoner.name == summoner_name,
                    Summoner.region == summoner.region
                ).first()
                
                if existing_summoner:
                    # Use the existing summoner if one with the same name and region exists
                    summoner = existing_summoner
                else:
                    session.add(summoner)
                    try:
                        session.commit()
                    except Exception as e:
                        session.rollback()
                        # If commit fails, try to find the summoner again in case of race condition
                        summoner = session.query(Summoner).filter(Summoner.puuid == puuid).first()
                        if not summoner:
                            # If still not found, re-raise the exception
                            raise
        
        # Create participant with all damage fields
        participant = Participant(
            match_id=match.match_id,
            participant_id=participant_id,
            team_id=participant_data.get('teamId', 0),
            summoner_puuid=puuid,
            summoner_name=participant_data.get('summonerName'),
            summoner_level=participant_data.get('summonerLevel'),
            profile_icon=participant_data.get('profileIcon'),
            champion_id=participant_data.get('championId', 0),
            champion_name=participant_data.get('championName'),
            champion_level=participant_data.get('champLevel'),
            kills=participant_data.get('kills', 0),
            deaths=participant_data.get('deaths', 0),
            assists=participant_data.get('assists', 0),
            kda=participant_data.get('challenges', {}).get('kda'),
            
            # Damage stats
            total_damage_dealt=participant_data.get('totalDamageDealt'),
            total_damage_taken=participant_data.get('totalDamageTaken'),
            damage_dealt_to_champions=participant_data.get('totalDamageDealtToChampions'),
            damage_dealt_to_objectives=participant_data.get('damageDealtToObjectives'),
            damage_self_mitigated=participant_data.get('damageSelfMitigated'),
            magic_damage_dealt=participant_data.get('magicDamageDealt'),
            magic_damage_dealt_to_champions=participant_data.get('magicDamageDealtToChampions'),
            physical_damage_dealt=participant_data.get('physicalDamageDealt'),
            physical_damage_dealt_to_champions=participant_data.get('physicalDamageDealtToChampions'),
            physical_damage_taken=participant_data.get('physicalDamageTaken'),
            true_damage_dealt=participant_data.get('trueDamageDealt'),
            true_damage_dealt_to_champions=participant_data.get('trueDamageDealtToChampions'),
            
            # Gold and CS
            gold_earned=participant_data.get('goldEarned'),
            gold_spent=participant_data.get('goldSpent'),
            total_minions_killed=participant_data.get('totalMinionsKilled'),
            neutral_minions_killed=participant_data.get('neutralMinionsKilled'),
            
            # Vision - using camelCase keys to match Riot API response
            vision_score=participant_data.get('visionScore'),
            vision_wards_bought=participant_data.get('visionWardsBoughtInGame'),
            wards_placed=participant_data.get('wardsPlaced'),
            wards_killed=participant_data.get('wardsKilled'),
            detector_wards_placed=participant_data.get('detectorWardsPlaced'),
            sight_wards_bought_in_game=participant_data.get('sightWardsBoughtInGame'),
            
            item0=participant_data.get('item0'),
            item1=participant_data.get('item1'),
            item2=participant_data.get('item2'),
            item3=participant_data.get('item3'),
            item4=participant_data.get('item4'),
            item5=participant_data.get('item5'),
            item6=participant_data.get('item6'),
            summoner1_id=participant_data.get('summoner1Id'),
            summoner2_id=participant_data.get('summoner2Id'),
            primary_style=participant_data.get('perks', {}).get('styles', [{}])[0].get('style') if participant_data.get('perks') else None,
            sub_style=participant_data.get('perks', {}).get('styles', [{}])[1].get('style') if participant_data.get('perks') and len(participant_data.get('perks', {}).get('styles', [])) > 1 else None,
            perks=participant_data.get('perks'),
            team_position=participant_data.get('teamPosition'),
            lane=participant_data.get('lane'),
            role=participant_data.get('role'),
            win=participant_data.get('win', False),
            first_blood_kill=participant_data.get('firstBloodKill', False),
            first_blood_assist=participant_data.get('firstBloodAssist', False),
            first_tower_kill=participant_data.get('firstTowerKill', False),
            first_tower_assist=participant_data.get('firstTowerAssist', False),
            double_kills=participant_data.get('doubleKills', 0),
            triple_kills=participant_data.get('tripleKills', 0),
            quadra_kills=participant_data.get('quadraKills', 0),
            penta_kills=participant_data.get('pentaKills', 0),
            turret_kills=participant_data.get('turretKills', 0),
            inhibitor_kills=participant_data.get('inhibitorKills', 0),
            time_ccing_others=participant_data.get('timeCCingOthers', 0),
            total_time_cc_dealt=participant_data.get('totalTimeCCDealt', 0),
            challenges=participant_data.get('challenges')
        )
        
        # Check if participant already exists to avoid duplicates
        existing_participant = session.query(Participant).filter(
            Participant.match_id == match.match_id,
            Participant.participant_id == participant_id
        ).first()
        
        if not existing_participant:
            session.add(participant)
    
    # Final commit for any remaining changes
    session.commit()
    return match, True

def process_summoner_match_history(
    api_client: RiotAPIClient,
    puuid: str,
    region: str = 'americas',
    count: int = 20,
    queue: Optional[int] = None,
    session: Optional[Session] = None,
    include_timeline: bool = True,
    only_requested_user: bool = True
) -> List[Match]:
    """
    Process a summoner's match history.
    
    Args:
        api_client: Initialized RiotAPIClient
        puuid: Player's PUUID
        region: Regional routing value (default: 'americas')
        count: Number of matches to process (max 100)
        queue: Queue ID to filter by (optional)
        session: Optional database session
        include_timeline: Whether to fetch and process timeline data (default: True)
        only_requested_user: If False, store data for all participants in each match (default: True)
        
    Returns:
        List of processed Match objects
    """
    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True
    
    try:
        # Ensure count is an integer and within valid range
        count_int = int(count) if count is not None else 20
        count_int = max(1, min(count_int, 100))  # Ensure count is between 1 and 100
        
        # Get match history - note: region is already set in the api_client
        match_ids = api_client.get_match_history(
            puuid=puuid,
            count=count_int,
            queue=queue,
            region=region
        )
        if not match_ids:
            return []
        
        processed_matches = []
        
        # Process each match
        for match_id in match_ids:
            try:
                match, _ = process_match_data(
                    api_client=api_client,
                    match_id=match_id,
                    region=region,
                    session=session,
                    include_timeline=include_timeline,
                    target_puuid=puuid,
                    only_requested_user=only_requested_user
                )
                if match:
                    processed_matches.append(match)
            except Exception as e:
                logger.error(f"Error processing match {match_id}: {str(e)}", exc_info=True)
                session.rollback()
        
        return processed_matches
        
    except Exception as e:
        logger.error(f"Error processing match history for PUUID {puuid}: {str(e)}", exc_info=True)
        if close_session and session:
            session.rollback()
        raise
    finally:
        if close_session and session:
            session.close()
