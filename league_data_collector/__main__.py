"""Main module for the League Data Collector package."""

def main():
    """Entry point for the application."""
    from .cli import main as cli_main
    cli_main()

if __name__ == "__main__":
    main()
