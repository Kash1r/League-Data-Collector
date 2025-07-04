# League of Legends Match Data Collector

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

A powerful command-line utility for retrieving, storing, and analyzing League of Legends match data using the official Riot Games API. Perfect for players looking to analyze their performance or developers building LoL-related tools.

## ✨ Features

- **Summoner Lookup**: Fetch detailed summoner information using Riot ID
- **Match History**: Retrieve and store up to 100 most recent matches
- **Complete Match Data**: Option to fetch all participants' data with `--all-participants`
- **Local SQLite Storage**: Efficient local database for match data
- **CSV Export**: Export to Excel-friendly CSV for analysis
- **Rate Limited**: Built-in rate limiting for API compliance
- **Cross-Platform**: Works on Windows, macOS, and Linux

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- [Riot Games Developer Account](https://developer.riotgames.com/)
- Valid Riot Games API Key

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/league-data-collector.git
   cd league-data-collector
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure your API key**
   Create a `.env` file in the project root:
   ```bash
   echo "RIOT_API_KEY=your_api_key_here" > .env
   ```
   > **Note**: Development API keys expire after 24 hours.

## 💻 Basic Usage

### Fetching Match Data

```bash
# Basic usage
python -m league_data_collector.cli --region na1 fetch "SummonerName#TAG"

# Fetch with options
python -m league_data_collector.cli --region na1 fetch "Kashir#7864" \
  --matches 20 \
  --all-participants \
  --queue 420  # Ranked Solo/Duo
```

### Exporting Data

```bash
# Export all tables to CSV
python -m league_data_collector.cli export tables --output-dir exports

# Export specific table (e.g., participants)
python -m league_data_collector.cli export tables --table participants

# Export individual match data
python -m league_data_collector.cli export matches --output-dir match_exports

# Filter exports by summoner name
python -m league_data_collector.cli export matches --summoner "Kashir"
```

## 📚 Command Reference

### Fetch Command
```bash
python -m league_data_collector.cli --region <code> fetch "Summoner#TAG" [options]
```

**Options:**
- `--region <code>`: Server region (e.g., na1, euw1, kr)
- `--matches <1-100>`: Number of matches to fetch (default: 20)
- `--queue <id>`: Filter by queue type (e.g., 420 for Ranked Solo/Duo)
- `--all-participants`: Include data for all players in each match
- `--force-update`: Refresh existing match data

### Export Commands

#### Export Tables
```bash
python -m league_data_collector.cli export tables [options]
```

**Options:**
- `--output-dir <dir>`: Output directory (default: 'exports')
- `--table <name>`: Table to export: 'summoners', 'matches', 'participants', 'teams', 'timelines', or 'all'

#### Export Matches
```bash
python -m league_data_collector.cli export matches [options]
```

**Options:**
- `--output-dir <dir>`: Output directory (default: 'match_exports')
- `--summoner <name>`: Filter by summoner name

## 🌍 Available Regions

| Code  | Region               |
|-------|----------------------|
| na1   | North America        |
| euw1  | Europe West          |
| eun1  | Europe Nordic & East |
| kr    | Korea                |
| br1   | Brazil               |
| la1   | Latin America North  |
| la2   | Latin America South  |
| oc1   | Oceania              |
| ru    | Russia               |
| tr1   | Turkey               |
| jp1   | Japan                |

## 📂 Data Structure

### File Locations
- **Database**: `league_data.db` (SQLite)
- **Exports**:
  - `exports/`: Individual database tables as CSV files
  - `match_exports/`: Complete match data (one file per match)

### Project Structure
```
league_data_collector/
├── cli.py               # Command-line interface
├── config.py            # Configuration and environment
├── database.py          # Database connection and schema
├── models/              # SQLAlchemy data models
│   ├── __init__.py
│   ├── base.py          # Base model class
│   ├── match.py         # Match data model
│   └── summoner.py      # Summoner data model
├── riot_api.py          # Riot API client
└── utils/               # Utility functions
    └── data_cleaning.py # Data processing utilities
```

## ⚠️ Important Notes

### Rate Limiting
- 20 requests per second
- 100 requests every 2 minutes

### Data Privacy
- All match data is stored locally in your project directory
- Your API key is only used for Riot API requests and never shared

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This project isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games or anyone officially involved in producing or managing League of Legends. League of Legends and Riot Games are trademarks or registered trademarks of Riot Games, Inc. League of Legends © Riot Games, Inc.
