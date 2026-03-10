import json
import os
import logging

logger = logging.getLogger(__name__)

# Use /tmp for writable storage in Railway (ephemeral but works for runtime)
# Falls back to local directory if /tmp is not available
def _get_storage_path():
    tmp_path = "/tmp/games.json"
    local_path = os.path.join(os.path.dirname(__file__), "games.json")

    # Prefer /tmp since it's always writable on Railway
    try:
        os.makedirs("/tmp", exist_ok=True)
        return tmp_path
    except Exception:
        return local_path

STORAGE_PATH = _get_storage_path()


def load_games() -> dict:
    """Load all games from JSON storage."""
    try:
        if os.path.exists(STORAGE_PATH):
            with open(STORAGE_PATH, "r") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Could not load games from {STORAGE_PATH}: {e}")
    return {}


def save_games(games: dict) -> bool:
    """Save all games to JSON storage."""
    try:
        os.makedirs(os.path.dirname(STORAGE_PATH) or ".", exist_ok=True)
        with open(STORAGE_PATH, "w") as f:
            json.dump(games, f, indent=2)
        return True
    except IOError as e:
        logger.error(f"Could not save games to {STORAGE_PATH}: {e}")
        return False


def get_game(game_id: str) -> dict | None:
    """Get a single game by ID."""
    games = load_games()
    return games.get(game_id)


def save_game(game_id: str, game_data: dict) -> bool:
    """Save a single game."""
    games = load_games()
    games[game_id] = game_data
    return save_games(games)


def delete_game(game_id: str) -> bool:
    """Delete a game by ID."""
    games = load_games()
    if game_id in games:
        del games[game_id]
        return save_games(games)
    return False


def cleanup_old_games(max_age_hours: int = 24) -> int:
    """Remove games older than max_age_hours. Returns count removed."""
    import time
    games = load_games()
    now = time.time()
    to_delete = []

    for game_id, game in games.items():
        created_at = game.get("created_at", now)
        if (now - created_at) > (max_age_hours * 3600):
            to_delete.append(game_id)

    for game_id in to_delete:
        del games[game_id]

    if to_delete:
        save_games(games)

    return len(to_delete)
