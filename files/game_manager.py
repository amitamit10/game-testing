import random
import string
import time
import logging
from storage import get_game, save_game, delete_game

logger = logging.getLogger(__name__)

MAX_PLAYERS = 10
MIN_PLAYERS = 2


def generate_game_id(length: int = 6) -> str:
    """Generate a short, readable game code."""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


def create_game(host_name: str, secret_word: str, host_socket_id: str) -> dict:
    """Create a new game and return game state."""
    game_id = generate_game_id()

    # Ensure unique ID
    while get_game(game_id):
        game_id = generate_game_id()

    host_player = {
        "id": host_socket_id,
        "name": host_name.strip(),
        "is_host": True,
        "is_spy": False,
        "joined_at": time.time(),
    }

    game = {
        "id": game_id,
        "secret_word": secret_word.strip(),
        "host_id": host_socket_id,
        "players": [host_player],
        "status": "lobby",  # lobby | playing | reveal
        "round": 1,
        "spy_id": None,
        "created_at": time.time(),
        "updated_at": time.time(),
    }

    save_game(game_id, game)
    logger.info(f"Game created: {game_id} by {host_name}")
    return game


def join_game(game_id: str, player_name: str, socket_id: str) -> tuple[dict | None, str | None]:
    """
    Add a player to a game.
    Returns (updated_game, error_message).
    """
    game = get_game(game_id)
    if not game:
        return None, "Game not found."

    if game["status"] != "lobby":
        return None, "Game has already started."

    if len(game["players"]) >= MAX_PLAYERS:
        return None, f"Game is full (max {MAX_PLAYERS} players)."

    # Check for duplicate names
    player_name = player_name.strip()
    existing_names = [p["name"].lower() for p in game["players"]]
    if player_name.lower() in existing_names:
        return None, "That name is already taken. Choose another."

    # Check if socket already joined
    for p in game["players"]:
        if p["id"] == socket_id:
            return game, None  # Already in game

    new_player = {
        "id": socket_id,
        "name": player_name,
        "is_host": False,
        "is_spy": False,
        "joined_at": time.time(),
    }

    game["players"].append(new_player)
    game["updated_at"] = time.time()
    save_game(game_id, game)
    return game, None


def start_game(game_id: str, requester_id: str) -> tuple[dict | None, str | None]:
    """
    Start the game: assign the spy, set status to playing.
    Returns (updated_game, error_message).
    """
    game = get_game(game_id)
    if not game:
        return None, "Game not found."

    if game["host_id"] != requester_id:
        return None, "Only the host can start the game."

    if len(game["players"]) < MIN_PLAYERS:
        return None, f"Need at least {MIN_PLAYERS} players to start."

    if game["status"] == "playing":
        return None, "Game is already in progress."

    # Pick a random spy
    spy = random.choice(game["players"])

    for p in game["players"]:
        p["is_spy"] = p["id"] == spy["id"]

    game["spy_id"] = spy["id"]
    game["status"] = "playing"
    game["updated_at"] = time.time()
    save_game(game_id, game)
    logger.info(f"Game {game_id} started. Spy: {spy['name']}")
    return game, None


def reveal_game(game_id: str, requester_id: str) -> tuple[dict | None, str | None]:
    """Reveal the spy and end the round."""
    game = get_game(game_id)
    if not game:
        return None, "Game not found."

    if game["host_id"] != requester_id:
        return None, "Only the host can reveal."

    if game["status"] != "playing":
        return None, "Game is not in progress."

    game["status"] = "reveal"
    game["updated_at"] = time.time()
    save_game(game_id, game)
    return game, None


def new_round(game_id: str, requester_id: str, new_secret_word: str) -> tuple[dict | None, str | None]:
    """
    Start a new round with same players. Optionally change the secret word.
    """
    game = get_game(game_id)
    if not game:
        return None, "Game not found."

    if game["host_id"] != requester_id:
        return None, "Only the host can start a new round."

    # Reset spy flags
    for p in game["players"]:
        p["is_spy"] = False

    # Pick new spy
    spy = random.choice(game["players"])
    for p in game["players"]:
        p["is_spy"] = p["id"] == spy["id"]

    game["spy_id"] = spy["id"]
    game["secret_word"] = new_secret_word.strip() if new_secret_word.strip() else game["secret_word"]
    game["status"] = "playing"
    game["round"] = game.get("round", 1) + 1
    game["updated_at"] = time.time()
    save_game(game_id, game)
    logger.info(f"Game {game_id} new round {game['round']}. Spy: {spy['name']}")
    return game, None


def remove_player(game_id: str, socket_id: str) -> dict | None:
    """Remove a player from a game. If host leaves, delete game."""
    game = get_game(game_id)
    if not game:
        return None

    if game["host_id"] == socket_id:
        delete_game(game_id)
        return None  # Signal game deleted

    game["players"] = [p for p in game["players"] if p["id"] != socket_id]
    game["updated_at"] = time.time()
    save_game(game_id, game)
    return game


def get_player_view(game: dict, socket_id: str) -> dict:
    """
    Return a filtered view of the game for a specific player.
    Players only see their own spy status. Everyone sees the word except the spy.
    """
    player_data = None
    for p in game["players"]:
        if p["id"] == socket_id:
            player_data = p
            break

    is_spy = player_data["is_spy"] if player_data else False
    is_host = player_data["is_host"] if player_data else False

    view = {
        "id": game["id"],
        "status": game["status"],
        "round": game["round"],
        "host_id": game["host_id"],
        "players": [
            {
                "id": p["id"],
                "name": p["name"],
                "is_host": p["is_host"],
                # Only reveal spy status to that player themselves, or during reveal
                "is_spy": p["is_spy"] if (game["status"] == "reveal" or p["id"] == socket_id) else False,
            }
            for p in game["players"]
        ],
        "is_spy": is_spy,
        "is_host": is_host,
        # Spy doesn't get the word; everyone else does (during playing)
        "secret_word": (
            game["secret_word"]
            if (game["status"] == "reveal" or not is_spy)
            else None
        ),
        "spy_name": (
            next((p["name"] for p in game["players"] if p["is_spy"]), None)
            if game["status"] == "reveal"
            else None
        ),
    }
    return view
