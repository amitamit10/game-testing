import os
import logging
from pathlib import Path

import uvicorn
import socketio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

import game_manager
from storage import cleanup_old_games

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Socket.IO ─────────────────────────────────────────────────────────────────
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    logger=False,
    engineio_logger=False,
)

# ── FastAPI ───────────────────────────────────────────────────────────────────
app = FastAPI(title="Spy Game", docs_url=None, redoc_url=None)

# Serve static client files
CLIENT_DIR = Path(__file__).parent.parent / "client"
if CLIENT_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(CLIENT_DIR)), name="static")

@app.get("/")
async def serve_index():
    index_path = CLIENT_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "Spy Game API running. Client files not found."}

@app.get("/health")
async def health():
    return {"status": "ok"}

# Wrap FastAPI with Socket.IO ASGI middleware
socket_app = socketio.ASGIApp(sio, other_asgi_app=app, socketio_path="/socket.io")

# Map to track socket_id -> game_id for cleanup on disconnect
socket_game_map: dict[str, str] = {}


# ── Socket.IO Events ──────────────────────────────────────────────────────────

@sio.event
async def connect(sid, environ):
    logger.info(f"Client connected: {sid}")


@sio.event
async def disconnect(sid):
    logger.info(f"Client disconnected: {sid}")
    game_id = socket_game_map.pop(sid, None)
    if not game_id:
        return

    updated_game = game_manager.remove_player(game_id, sid)

    if updated_game is None:
        # Host left — game deleted, notify room
        await sio.emit("game_deleted", {"message": "Host left. Game ended."}, room=game_id)
        logger.info(f"Game {game_id} deleted (host disconnected)")
    else:
        # Notify remaining players with updated lobby
        await broadcast_lobby_update(game_id, updated_game)

    await sio.leave_room(sid, game_id)


@sio.event
async def create_game(sid, data):
    """
    data: { host_name, secret_word }
    """
    host_name = (data.get("host_name") or "").strip()
    secret_word = (data.get("secret_word") or "").strip()

    if not host_name:
        await sio.emit("error", {"message": "Host name is required."}, to=sid)
        return
    if not secret_word:
        await sio.emit("error", {"message": "Secret word is required."}, to=sid)
        return

    game = game_manager.create_game(host_name, secret_word, sid)
    socket_game_map[sid] = game["id"]
    await sio.enter_room(sid, game["id"])

    view = game_manager.get_player_view(game, sid)
    await sio.emit("game_created", view, to=sid)
    logger.info(f"[{game['id']}] Game created by {host_name}")


@sio.event
async def join_game(sid, data):
    """
    data: { game_id, player_name }
    """
    game_id = (data.get("game_id") or "").strip().upper()
    player_name = (data.get("player_name") or "").strip()

    if not game_id:
        await sio.emit("error", {"message": "Game ID is required."}, to=sid)
        return
    if not player_name:
        await sio.emit("error", {"message": "Player name is required."}, to=sid)
        return

    game, error = game_manager.join_game(game_id, player_name, sid)
    if error:
        await sio.emit("error", {"message": error}, to=sid)
        return

    socket_game_map[sid] = game_id
    await sio.enter_room(sid, game_id)

    view = game_manager.get_player_view(game, sid)
    await sio.emit("game_joined", view, to=sid)

    # Notify all players in lobby
    await broadcast_lobby_update(game_id, game)
    logger.info(f"[{game_id}] {player_name} joined")


@sio.event
async def start_game(sid, data):
    """
    data: { game_id }
    """
    game_id = (data.get("game_id") or "").strip().upper()

    game, error = game_manager.start_game(game_id, sid)
    if error:
        await sio.emit("error", {"message": error}, to=sid)
        return

    # Send personalised view to each player
    await broadcast_game_state(game_id, game)
    logger.info(f"[{game_id}] Game started")


@sio.event
async def reveal(sid, data):
    """
    data: { game_id }
    """
    game_id = (data.get("game_id") or "").strip().upper()

    game, error = game_manager.reveal_game(game_id, sid)
    if error:
        await sio.emit("error", {"message": error}, to=sid)
        return

    await broadcast_game_state(game_id, game)
    logger.info(f"[{game_id}] Reveal triggered")


@sio.event
async def new_round(sid, data):
    """
    data: { game_id, secret_word }
    """
    game_id = (data.get("game_id") or "").strip().upper()
    secret_word = (data.get("secret_word") or "").strip()

    if not secret_word:
        await sio.emit("error", {"message": "Secret word is required for the new round."}, to=sid)
        return

    game, error = game_manager.new_round(game_id, sid, secret_word)
    if error:
        await sio.emit("error", {"message": error}, to=sid)
        return

    await broadcast_game_state(game_id, game)
    logger.info(f"[{game_id}] New round started")


# ── Broadcast Helpers ─────────────────────────────────────────────────────────

async def broadcast_lobby_update(game_id: str, game: dict):
    """Send lobby player list to all in room (status-agnostic)."""
    players_public = [
        {"id": p["id"], "name": p["name"], "is_host": p["is_host"]}
        for p in game["players"]
    ]
    await sio.emit(
        "lobby_update",
        {
            "game_id": game_id,
            "players": players_public,
            "status": game["status"],
            "round": game.get("round", 1),
        },
        room=game_id,
    )


async def broadcast_game_state(game_id: str, game: dict):
    """Send personalised game state to every player in the room."""
    for player in game["players"]:
        view = game_manager.get_player_view(game, player["id"])
        await sio.emit("game_state", view, to=player["id"])


# ── Startup / Shutdown ────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    removed = cleanup_old_games(max_age_hours=24)
    if removed:
        logger.info(f"Cleaned up {removed} old game(s)")
    logger.info("Spy Game server started")


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "main:socket_app",
        host="0.0.0.0",
        port=port,
        log_level="info",
    )
