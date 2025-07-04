"""Riot Games API client for fetching League of Legends data."""
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import requests
from ratelimit import limits, sleep_and_retry
from requests import Response

from .config import settings

# Set up logging
logger = logging.getLogger(__name__)

class RiotAPIError(Exception):
    """Base exception for Riot API errors."""
    pass

class RiotAPIClient:
    """Client for interacting with the Riot Games API."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Riot API client.
        
        Args:
            api_key: Optional API key. If not provided, uses the one from settings.
        """
        self.api_key = api_key or settings.RIOT_API_KEY
        self.rate_limit = settings.RIOT_API_RATE_LIMIT
        
        if not self.api_key:
            raise ValueError("Riot API key is required")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get the headers for API requests."""
        return {
            "X-Riot-Token": self.api_key,
            "Accept": "application/json"
        }
    
    @sleep_and_retry
    @limits(calls=20, period=1)  # 20 requests per second
    def _make_request(self, url: str, params: Optional[Dict] = None) -> Union[Dict, List]:
        """Make a request to the Riot API with rate limiting."""
        try:
            response = requests.get(
                url,
                headers=self._get_headers(),
                params=params or {},
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response content: {e.response.text}")
            raise RiotAPIError(f"Failed to fetch data: {str(e)}")
    
    def get_account_by_riot_id(self, game_name: str, tag_line: str) -> Dict[str, Any]:
        """Get account data by Riot ID (game name and tag line).
        
        Args:
            game_name: The in-game name of the player
            tag_line: The tag line (usually region code like NA1, EUW1, etc.)
            
        Returns:
            Dict containing account data including puuid
        """
        url = f"https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
        return self._make_request(url)
    
    def get_match_history(
        self, 
        puuid: str,
        count: int = 20,
        queue: Optional[int] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        start: int = 0,
        type: Optional[str] = None,
        region: str = 'na1'  # Platform routing value (na1, euw1, etc.)
    ) -> List[str]:
        """Get match history for a summoner using match-v5 endpoint.
        
        Args:
            puuid: The player's PUUID
            count: Number of matches to return (default: 20, max: 100)
            queue: Queue ID to filter by (optional)
            start_time: Epoch timestamp in seconds (optional)
            end_time: Epoch timestamp in seconds (optional)
            start: Start index (for pagination)
            type: Type of match to filter by (e.g., 'ranked', 'normal')
            region: Platform routing value (e.g., 'na1', 'euw1', 'kr')
            
        Returns:
            List of match IDs
        """
        # Convert platform routing value to regional routing value
        region_mapping = {
            'na1': 'americas',
            'br1': 'americas',
            'la1': 'americas',
            'la2': 'americas',
            'oc1': 'americas',
            'eun1': 'europe',
            'euw1': 'europe',
            'tr1': 'europe',
            'ru': 'europe',
            'jp1': 'asia',
            'kr': 'asia',
        }
        
        regional_route = region_mapping.get(region.lower(), 'americas')
        url = f"https://{regional_route}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
        
        params = {
            'start': start,
            'count': min(int(count), 100),  # Ensure count is an integer and max 100
        }
        
        if queue is not None:
            params['queue'] = int(queue)  # Ensure queue is an integer
        if start_time is not None:
            params['startTime'] = start_time
        if end_time is not None:
            params['endTime'] = end_time
        if type is not None:
            params['type'] = type
            
        logger.info(f"Fetching match history for PUUID: {puuid}")
        logger.info(f"API Request - URL: {url}, Params: {params}")
        
        try:
            match_ids = self._make_request(url, params=params)
            logger.info(f"Received {len(match_ids)} match IDs")
            if not match_ids:
                logger.warning("No match IDs returned. This could be normal if the player has no recent matches.")
            return match_ids
        except Exception as e:
            logger.error(f"Error fetching match history: {str(e)}")
            raise
    
    def get_match_details(self, match_id: str, region: str = 'na1') -> Dict[str, Any]:
        """Get detailed match data by match ID using match-v5 endpoint.
        
        Args:
            match_id: The match ID to look up
            region: Platform routing value (e.g., 'na1', 'euw1', 'kr')
            
        Returns:
            Dict containing match data
        """
        regional_route = self._get_regional_route(region)
        url = f"https://{regional_route}.api.riotgames.com/lol/match/v5/matches/{match_id}"
        return self._make_request(url)
        
    def get_match_timeline(self, match_id: str, region: str = 'na1') -> Dict[str, Any]:
        """Get detailed timeline data for a match using match-v5 endpoint.
        
        Args:
            match_id: The match ID to look up
            region: Platform routing value (e.g., 'na1', 'euw1', 'kr')
            
        Returns:
            Dict containing match timeline data with events and frames
        """
        regional_route = self._get_regional_route(region)
        url = f"https://{regional_route}.api.riotgames.com/lol/match/v5/matches/{match_id}/timeline"
        return self._make_request(url)
        
    def _get_regional_route(self, region: str) -> str:
        """Convert platform routing value to regional routing value.
        
        Args:
            region: Platform routing value (e.g., 'na1', 'euw1', 'kr')
            
        Returns:
            Regional routing value (americas, europe, asia, sea)
        """
        region_mapping = {
            # Americas
            'na1': 'americas',
            'br1': 'americas',
            'la1': 'americas',
            'la2': 'americas',
            'oc1': 'americas',
            # Europe
            'eun1': 'europe',
            'euw1': 'europe',
            'tr1': 'europe',
            'ru': 'europe',
            # Asia
            'jp1': 'asia',
            'kr': 'asia',
            # Southeast Asia
            'ph2': 'sea',
            'sg2': 'sea',
            'th2': 'sea',
            'tw2': 'sea',
            'vn2': 'sea'
        }
        return region_mapping.get(region.lower(), 'americas')
    
    def get_summoner_by_puuid(self, puuid: str) -> Dict[str, Any]:
        """Get summoner data by PUUID using account-v1 endpoint.
        
        Args:
            puuid: The player's PUUID
            
        Returns:
            Dict containing summoner data
        """
        url = f"https://americas.api.riotgames.com/riot/account/v1/accounts/by-puuid/{puuid}"
        return self._make_request(url)
    
    def get_summoner_info(self, game_name: str, tag_line: str) -> Dict[str, Any]:
        """Get all available summoner information by Riot ID.
        
        Args:
            game_name: The in-game name of the player
            tag_line: The tag line (usually region code like NA1, EUW1, etc.)
            
        Returns:
            Dict containing account and match history data
        """
        # First get account info to get PUUID
        account = self.get_account_by_riot_id(game_name, tag_line)
        puuid = account.get('puuid')
        
        if not puuid:
            raise RiotAPIError("Could not retrieve PUUID for the given Riot ID")
        
        # Get match history
        match_ids = self.get_match_history(puuid, count=5)  # Get last 5 matches by default
        
        # Get details for each match
        matches = []
        for match_id in match_ids:
            try:
                match_details = self.get_match_details(match_id)
                matches.append(match_details)
            except RiotAPIError as e:
                logger.warning(f"Failed to fetch match {match_id}: {str(e)}")
        
        return {
            'account': account,
            'matches': matches,
            'match_count': len(matches)
        }
