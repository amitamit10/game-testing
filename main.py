import os
import sys
import logging
from pathlib import Path

# Ensure server/ is on sys.path so imports (game_manager, storage) work
# whether uvicorn is launched from repo root OR from server/ directory.
_SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_DIR)

import socketio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

import game_manager as gm

# --------------------------------------------------------------------------- #
#  Logging                                                                     #
# --------------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
#  App setup                                                                   #
# --------------------------------------------------------------------------- #
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    logger=False,
    engineio_logger=False,
)

fastapi_app = FastAPI(title="Spy Word Game")

# Serve static client files — works whether we run from repo root or server/
_HERE = Path(__file__).parent          # server/
CLIENT_DIR = _HERE.parent / "client"   # ../client  (repo-root/client/)

if CLIENT_DIR.exists():
    fastapi_app.mount("/static", StaticFiles(directory=str(CLIENT_DIR)), name="static")
else:
    logger.warning("client/ directory not found at %s", CLIENT_DIR)


@fastapi_app.get("/")
async def serve_index():
    index = CLIENT_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"status": "running", "message": "client/ not found"}


@fastapi_app.get("/health")
async def health():
    return {"status": "ok"}


# Wrap FastAPI with Socket.IO ASGI middleware (THIS is the ASGI app Railway runs)
app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app)


# --------------------------------------------------------------------------- #
#  Helpers                                                                     #
# --------------------------------------------------------------------------- #
async def _broadcast_game(code: str):
    """Emit updated game state to every player in the room."""
    game = gm.get_game(code)
    if not game:
        return
    for pid, player in game["players"].items():
        state = gm.public_game_state(game, pid)
        await sio.emit("game_update", state, room=player["sid"])


# --------------------------------------------------------------------------- #
#  Socket.IO events                                                            #
# --------------------------------------------------------------------------- #

@sio.event
async def connect(sid, environ):
    logger.info("Client connected: %s", sid)


@sio.event
async def disconnect(sid):
    logger.info("Client disconnected: %s", sid)
    code = gm.find_game_by_sid(sid)
    if code:
        gm.update_player_connection(code, sid, connected=False)
        await _broadcast_game(code)


@sio.on("create_game")
async def on_create_game(sid, data):
    host_name   = str(data.get("host_name",   "Host")).strip()[:30] or "Host"
    secret_word = str(data.get("secret_word", "")).strip()[:100]
    if not secret_word:
        await sio.emit("error", {"message": "Secret word is required."}, room=sid)
        return
    game = gm.create_game(host_name, sid, secret_word)
    await sio.enter_room(sid, game["code"])
    await sio.emit("game_update", gm.public_game_state(game, sid), room=sid)


@sio.on("join_game")
async def on_join_game(sid, data):
    code        = str(data.get("code",        "")).strip().upper()
    player_name = str(data.get("player_name", "Player")).strip()[:30] or "Player"
    game = gm.join_game(code, player_name, sid)
    if not game:
        await sio.emit("error", {"message": "Game not found, full, or already started."}, room=sid)
        return
    await sio.enter_room(sid, code)
    await _broadcast_game(code)


@sio.on("start_game")
async def on_start_game(sid, data):
    code = str(data.get("code", "")).strip().upper()
    game = gm.start_game(code, sid)
    if not game:
        await sio.emit("error", {"message": "Cannot start game."}, room=sid)
        return
    await _broadcast_game(code)


@sio.on("new_round")
async def on_new_round(sid, data):
    code     = str(data.get("code",     "")).strip().upper()
    new_word = str(data.get("new_word", "")).strip()[:100] or None
    game = gm.new_round(code, sid, new_word)
    if not game:
        await sio.emit("error", {"message": "Cannot start new round."}, room=sid)
        return
    await _broadcast_game(code)


@sio.on("cast_vote")
async def on_cast_vote(sid, data):
    code       = str(data.get("code",      "")).strip().upper()
    target_sid = str(data.get("target_id", "")).strip()
    game = gm.cast_vote(code, sid, target_sid)
    if not game:
        await sio.emit("error", {"message": "Cannot cast vote."}, room=sid)
        return
    await _broadcast_game(code)


@sio.on("reveal_spy")
async def on_reveal_spy(sid, data):
    code = str(data.get("code", "")).strip().upper()
    from storage import load_games, save_games
    games = load_games()
    game  = games.get(code)
    if not game or game["host_id"] != sid:
        return
    game["state"] = "ended"
    games[code]   = game
    save_games(games)
    await _broadcast_game(code)


# --------------------------------------------------------------------------- #
#  Entry point (local dev)                                                     #
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)