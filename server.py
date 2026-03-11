import json
import os
import random
import string
from datetime import datetime
from flask import Flask, request, send_from_directory
from flask_socketio import SocketIO, join_room, leave_room, emit

app = Flask(__name__, static_folder="client")
app.config["SECRET_KEY"] = "spy-game-secret-2024"
socketio = SocketIO(app, cors_allowed_origins="*", logger=False, engineio_logger=False)

GAMES_FILE = "games.json"

# ─── Storage ────────────────────────────────────────────────────────────────

def load_games():
    if not os.path.exists(GAMES_FILE):
        save_games({})
    with open(GAMES_FILE, "r") as f:
        return json.load(f)

def save_games(games):
    with open(GAMES_FILE, "w") as f:
        json.dump(games, f, indent=2)

def get_game(game_id):
    return load_games().get(game_id)

def set_game(game_id, data):
    games = load_games()
    games[game_id] = data
    save_games(games)

def delete_game(game_id):
    games = load_games()
    games.pop(game_id, None)
    save_games(games)

# ─── Helpers ────────────────────────────────────────────────────────────────

def generate_game_id():
    games = load_games()
    while True:
        gid = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if gid not in games:
            return gid

def make_player(name, player_id, is_host=False):
    return {
        "id": player_id,
        "name": name,
        "is_host": is_host,
        "joined_at": datetime.utcnow().isoformat(),
    }

# ─── HTTP Routes ─────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("client", "index.html")

@app.route("/<path:path>")
def static_files(path):
    return send_from_directory("client", path)

# ─── Socket Events ───────────────────────────────────────────────────────────

@socketio.on("create_game")
def on_create_game(data):
    name = data.get("name", "").strip()
    if not name:
        emit("error", {"message": "Name is required"})
        return

    game_id = generate_game_id()
    player_id = request.sid
    player = make_player(name, player_id, is_host=True)

    game = {
        "game_id": game_id,
        "host_id": player_id,
        "status": "lobby",     # lobby | setup | playing
        "players": [player],
        "spy": None,
        "word": None,
        "round": 0,
    }
    set_game(game_id, game)
    join_room(game_id)

    emit("game_created", {
        "game_id": game_id,
        "player_id": player_id,
        "player": player,
        "game": game,
    })
    emit("lobby_update", {"players": game["players"], "game_id": game_id}, to=game_id)

@socketio.on("join_game")
def on_join_game(data):
    name = data.get("name", "").strip()
    game_id = data.get("game_id", "").strip().upper()

    if not name or not game_id:
        emit("error", {"message": "Name and Game ID are required"})
        return

    game = get_game(game_id)
    if not game:
        emit("error", {"message": "Game not found. Check your Game ID."})
        return

    if game["status"] != "lobby":
        emit("error", {"message": "Game already started. Cannot join."})
        return

    if len(game["players"]) >= 10:
        emit("error", {"message": "Game is full (max 10 players)."})
        return

    # Check duplicate name
    existing_names = [p["name"].lower() for p in game["players"]]
    if name.lower() in existing_names:
        emit("error", {"message": f'Name "{name}" is already taken.'})
        return

    player_id = request.sid
    player = make_player(name, player_id)
    game["players"].append(player)
    set_game(game_id, game)
    join_room(game_id)

    emit("game_joined", {
        "game_id": game_id,
        "player_id": player_id,
        "player": player,
        "game": game,
    })

    # Notify everyone in the room
    socketio.emit("lobby_update", {
        "players": game["players"],
        "game_id": game_id,
        "new_player": name,
    }, to=game_id)

@socketio.on("start_game")
def on_start_game(data):
    game_id = data.get("game_id")
    spy_name = data.get("spy")
    word = data.get("word", "").strip()

    if not game_id or not spy_name or not word:
        emit("error", {"message": "Spy and word are required."})
        return

    game = get_game(game_id)
    if not game:
        emit("error", {"message": "Game not found."})
        return

    if game["host_id"] != request.sid:
        emit("error", {"message": "Only the host can start the game."})
        return

    if len(game["players"]) < 3:
        emit("error", {"message": "Need at least 3 players to start."})
        return

    game["status"] = "playing"
    game["spy"] = spy_name
    game["word"] = word
    game["round"] = game.get("round", 0) + 1
    set_game(game_id, game)

    # Send personalised role to each connected player
    for player in game["players"]:
        pid = player["id"]
        if player["name"] == spy_name:
            role_data = {
                "role": "spy",
                "message": "You are the spy.",
                "round": game["round"],
                "player_count": len(game["players"]),
            }
        else:
            role_data = {
                "role": "agent",
                "word": word,
                "round": game["round"],
                "player_count": len(game["players"]),
            }
        socketio.emit("role_assigned", role_data, to=pid)

    # Broadcast generic game_started (no sensitive data)
    socketio.emit("game_started", {
        "round": game["round"],
        "player_count": len(game["players"]),
    }, to=game_id)

@socketio.on("new_round")
def on_new_round(data):
    game_id = data.get("game_id")
    game = get_game(game_id)

    if not game:
        emit("error", {"message": "Game not found."})
        return

    if game["host_id"] != request.sid:
        emit("error", {"message": "Only the host can start a new round."})
        return

    game["status"] = "lobby"
    game["spy"] = None
    game["word"] = None
    set_game(game_id, game)

    socketio.emit("round_reset", {
        "players": game["players"],
        "game_id": game_id,
    }, to=game_id)

@socketio.on("disconnect")
def on_disconnect():
    sid = request.sid
    games = load_games()
    for game_id, game in list(games.items()):
        players_before = len(game["players"])
        game["players"] = [p for p in game["players"] if p["id"] != sid]

        if len(game["players"]) == 0:
            # Empty room — delete it
            del games[game_id]
        else:
            # If host left, promote next player
            if game["host_id"] == sid and game["players"]:
                game["players"][0]["is_host"] = True
                game["host_id"] = game["players"][0]["id"]
                new_host_name = game["players"][0]["name"]
                socketio.emit("host_changed", {"new_host": new_host_name}, to=game_id)

            if len(game["players"]) < players_before:
                games[game_id] = game
                socketio.emit("lobby_update", {
                    "players": game["players"],
                    "game_id": game_id,
                }, to=game_id)

    save_games(games)

if __name__ == "__main__":
    if not os.path.exists(GAMES_FILE):
        save_games({})
    print("\n🕵️  SPY GAME SERVER")
    print("━" * 40)
    print("→  http://localhost:5050")
    print("━" * 40 + "\n")
    socketio.run(app, host="0.0.0.0", port=5050, debug=False, allow_unsafe_werkzeug=True)
