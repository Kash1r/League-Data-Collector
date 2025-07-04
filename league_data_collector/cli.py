"""Command-line interface for the League Data Collector."""
import argparse
import logging
import os
import sys
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import joinedload

from dotenv import load_dotenv

from sqlalchemy.orm import Session, joinedload

from . import __version__
from .config import settings, validate_config
from .database import SessionLocal
from .models import Summoner, Match, Participant, MatchTimeline
from .riot_api import RiotAPIClient, RiotAPIError
from .utils.timeline_analyzer import get_objective_participation, analyze_timeline_stats
from .utils.data_cleaning import process_summoner_data, process_summoner_match_history

def format_time(seconds: int) -> str:
    """Format seconds into MM:SS format.
    
    Args:
        seconds: Number of seconds to format
        
    Returns:
        str: Formatted time string (MM:SS)
    """
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes}:{seconds:02d}"

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('league_data_collector.log')
    ]
)
logger = logging.getLogger(__name__)

def setup_argparse() -> argparse.ArgumentParser:
    """Set up command line argument parsing."""
    parser = argparse.ArgumentParser(
        description='League of Legends Data Collector - Fetch and analyze summoner match data.'
    )
    
    # Global arguments
    parser.add_argument(
        '--region', 
        type=str, 
        default='na1',
        help='Region code (e.g., na1, euw1, kr). Default: na1'
    )
    parser.add_argument(
        '--debug', 
        action='store_true',
        help='Enable debug logging'
    )
    
    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Fetch command
    fetch_parser = subparsers.add_parser('fetch', help='Fetch data for a summoner')
    fetch_parser.add_argument('summoner_name', type=str, help='Summoner name to look up')
    fetch_parser.add_argument(
        '--matches', 
        type=int, 
        default=20,
        help='Number of matches to fetch (max 100). Default: 20'
    )
    fetch_parser.add_argument(
        '--queue',
        type=int,
        help='Queue ID to filter matches (e.g., 420 for Ranked Solo/Duo)'
    )
    fetch_parser.add_argument(
        '--all-participants', 
        action='store_true',
        dest='all_participants',
        help='Fetch data for all participants in each match (default: only requested user)'
    )
    # Keep the old --all-players for backward compatibility
    fetch_parser.add_argument(
        '--all-players', 
        action='store_true',
        dest='all_participants',
        help=argparse.SUPPRESS  # Hide from help as we prefer --all-participants
    )
    fetch_parser.add_argument(
        '--force-update',
        action='store_true',
        help='Force update even if data already exists'
    )
    
    # DB command
    db_parser = subparsers.add_parser('db', help='Database operations')
    db_subparsers = db_parser.add_subparsers(dest='db_command', help='Database command')
    
    # DB init
    db_init_parser = db_subparsers.add_parser('init', help='Initialize the database')
    
    # DB reset
    db_reset_parser = db_subparsers.add_parser('reset', help='Reset the database (WARNING: deletes all data)')
    
    # DB stats
    db_stats_parser = db_subparsers.add_parser('stats', help='Show database statistics')
    
    # Export subcommand
    export_parser = subparsers.add_parser('export', help='Export data to various formats')
    export_subparsers = export_parser.add_subparsers(dest='export_type', required=True)
    
    # Export all tables
    export_all_parser = export_subparsers.add_parser('all', help='Export all database tables to CSV')
    export_all_parser.add_argument(
        '--output-dir',
        type=str,
        default='exports',
        help='Output directory for CSV files (default: exports)'
    )
    
    # Export specific table
    export_table_parser = export_subparsers.add_parser('table', help='Export a specific table to CSV')
    export_table_parser.add_argument(
        'table',
        type=str,
        help='Name of the table to export (e.g., summoners, matches, participants)'
    )
    export_table_parser.add_argument(
        '--output-dir',
        type=str,
        default='exports',
        help='Output directory for CSV file (default: exports)'
    )
    
    # Export matches
    matches_parser = export_subparsers.add_parser('matches', help='Export match data with all related information')
    matches_parser.add_argument(
        '--output-dir',
        type=str,
        default='match_exports',
        help='Directory to save match CSV files (default: match_exports)'
    )
    matches_parser.add_argument(
        '--summoner',
        type=str,
        help='Summoner name to filter matches (optional)'
    )
    
    # Export objectives and gold leads
    objectives_parser = export_subparsers.add_parser('objectives', 
        help='Export gold leads and objective data for matches')
    objectives_parser.add_argument(
        '--output-dir',
        type=str,
        default='objective_exports',
        help='Directory to save objective CSV files (default: objective_exports)'
    )
    objectives_parser.add_argument(
        '--summoner',
        type=str,
        help='Summoner name to filter matches (optional)'
    )
    
    return parser

def fetch_summoner_data(args) -> None:
    """Fetch and store summoner data and match history."""
    logger.info(f"Fetching data for summoner: {args.summoner_name}")
    
    # Initialize API client
    try:
        api_client = RiotAPIClient()
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)
    
    # Process summoner data
    with SessionLocal() as session:
        try:
            # Get or create summoner
            summoner, is_new = process_summoner_data(
                api_client=api_client,
                summoner_name=args.summoner_name,
                region=args.region,
                session=session
            )
            
            if not summoner:
                logger.error(f"Could not find or create summoner: {args.summoner_name}")
                return
                
            # Only fetch match history if this is a new summoner or if forced
            if is_new or getattr(args, 'force', False):
                logger.info(f"Fetching match history for {summoner.name}...")
                matches = process_summoner_match_history(
                    api_client=api_client,
                    puuid=summoner.puuid,
                    region=args.region,
                    count=args.matches,
                    queue=args.queue,
                    session=session,
                    only_requested_user=not getattr(args, 'all_participants', False)
                )
                
                logger.info(f"Processed {len(matches)} matches for {summoner.name}")
        
        except RiotAPIError as e:
            logger.error(f"Riot API error: {str(e)}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Error processing summoner data: {str(e)}", exc_info=True)
            sys.exit(1)

def write_to_file(filename, content):
    """Helper function to write content to a file."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"Output written to {filename}")
    except Exception as e:
        logger.error(f"Error writing to file: {e}")

def handle_db_operations(args) -> None:
    """Handle database operations."""
    if args.db_command == 'init':
        from .database import create_tables
        print("Initializing database...")
        create_tables()
        print("Database initialized successfully.")
    
    elif args.db_command == 'reset':
        confirm = input("WARNING: This will delete all data. Are you sure? (y/n): ")
        if confirm.lower() == 'y':
            from .database import reset_database
            print("Resetting database...")
            reset_database()
            print("Database reset complete.")
    
    elif args.db_command == 'stats':
        from .database import SessionLocal
        from .models import Summoner, Match, Participant
        
        with SessionLocal() as session:
            summoner_count = session.query(Summoner).count()
            match_count = session.query(Match).count()
            participant_count = session.query(Participant).count()
            
            print("\n=== Database Statistics ===")
            print(f"Summoners: {summoner_count}")
            print(f"Matches: {match_count}")
            print(f"Participants: {participant_count}")
    
    else:
        print("Unknown database command. Use 'init', 'reset', or 'stats'.")

def export_data(args) -> None:
    """Export database data to CSV files."""
    from .utils.export_utils import export_all_tables, export_to_csv, export_match_data
    from .utils.objective_export_utils import export_objectives_and_gold
    from .database import SessionLocal
    
    session = SessionLocal()
    
    try:
        if hasattr(args, 'export_type'):
            if args.export_type == 'matches':
                # Handle match-based export
                logger.info(f"Exporting match data to directory: {args.output_dir}")
                if args.summoner:
                    logger.info(f"Filtering matches for summoner: {args.summoner}")
                
                results = export_match_data(
                    session=session,
                    output_dir=args.output_dir,
                    summoner_name=args.summoner
                )
                
                # Log results
                for match_id, result in results.items():
                    if result.startswith('Error'):
                        logger.error(f"{match_id}: {result}")
                    else:
                        logger.info(f"Exported {match_id} to {result}")
            
            elif args.export_type == 'objectives':
                # Handle objectives export
                logger.info(f"Exporting objectives data to directory: {args.output_dir}")
                if args.summoner:
                    logger.info(f"Filtering matches for summoner: {args.summoner}")
                
                results = export_objectives_and_gold(
                    session=session,
                    output_dir=args.output_dir,
                    summoner_name=args.summoner
                )
                
                # Log results
                for match_id, result in results.items():
                    if result.startswith('Error'):
                        logger.error(f"{match_id}: {result}")
                    else:
                        logger.info(f"Exported objectives for {match_id} to {result}")
            
            elif args.export_type == 'table':
                # Handle table-based export
                if hasattr(args, 'table') and args.table != 'all':
                    from ..models import Base
                    model_dict = {cls.__tablename__: cls for cls in Base._decl_class_registry.values() 
                                if hasattr(cls, '__tablename__')}
                    
                    if args.table not in model_dict:
                        logger.error(f"Unknown table: {args.table}")
                        logger.info(f"Available tables: {', '.join(model_dict.keys())}")
                        return
                        
                    logger.info(f"Exporting {args.table} to directory: {args.output_dir}")
                    try:
                        filepath = export_to_csv(session, model_dict[args.table], args.output_dir)
                        logger.info(f"Exported {args.table} to {filepath}")
                    except Exception as e:
                        logger.error(f"Error exporting {args.table}: {str(e)}")
                else:
                    # Export all tables
                    logger.info(f"Exporting all tables to directory: {args.output_dir}")
                    results = export_all_tables(session, args.output_dir)
                    for table, result in results.items():
                        if isinstance(result, str) and result.startswith('Error'):
                            logger.error(f"{table}: {result}")
                        else:
                            logger.info(f"Exported {table} to {result}")
            
            else:
                logger.error(f"Unknown export type: {args.export_type}")
    
    except Exception as e:
        logger.error(f"Error during export: {str(e)}", exc_info=args.debug)
    finally:
        session.close()

def main() -> None:
    """Main entry point for the CLI."""
    # Load environment variables
    load_dotenv()
    
    # Parse command line arguments
    parser = setup_argparse()
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.getLogger().setLevel(log_level)
    
    # Validate configuration
    is_valid, errors = validate_config()
    if not is_valid and not (hasattr(args, 'command') and args.command in ['db', 'export'] and 
                           (not hasattr(args, 'db_command') or args.db_command == 'init')):
        for error in errors:
            logger.error(error)
        sys.exit(1)
    
    # Route to appropriate handler
    if not hasattr(args, 'command') or args.command is None:
        parser.print_help()
        return
    
    try:
        if args.command == 'fetch':
            fetch_summoner_data(args)
        elif args.command == 'db':
            handle_db_operations(args)
        elif args.command == 'export':
            export_data(args)
        else:
            parser.print_help()
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}", exc_info=args.debug)
        sys.exit(1)

if __name__ == "__main__":
    main()
