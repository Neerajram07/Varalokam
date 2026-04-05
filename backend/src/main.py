"""
Varalokam — Main Server Entry Point

Starts an aiohttp web server with Socket.IO for real-time multiplayer
drawing and guessing game.

Usage:
    python -m src.main
"""

import logging
import os
import sys

from aiohttp import web
import socketio

from .config import config
from .services.room_manager import room_manager
from .socket_handlers.room_handler import register_room_handlers
from .socket_handlers.game_handler import (
    register_game_handlers,
    handle_drawer_disconnect,
    cleanup_room_timers,
)
from .socket_handlers.draw_handler import register_draw_handlers
from .socket_handlers.chat_handler import register_chat_handlers

# ── Logging Setup ─────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if config.DEBUG else logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(name)-25s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("varalokam")


# ── Socket.IO Server ─────────────────────────────────────
sio = socketio.AsyncServer(
    async_mode="aiohttp",
    cors_allowed_origins=config.CORS_ORIGINS if not config.DEBUG else "*",
    ping_interval=25,
    ping_timeout=60,
    max_http_buffer_size=1_000_000,  # 1MB max message size
    logger=config.DEBUG,
    engineio_logger=False,
)

# ── aiohttp Web App ──────────────────────────────────────
app = web.Application()
sio.attach(app)


# ── Register All Socket Handlers ─────────────────────────
register_room_handlers(sio)
register_game_handlers(sio)
register_draw_handlers(sio)
register_chat_handlers(sio)


# ── Core Socket Events ───────────────────────────────────

@sio.event
async def connect(sid, environ, auth=None):
    """Handle new client connection."""
    remote = environ.get("REMOTE_ADDR", "unknown")
    logger.info(f"✦ Client connected: {sid} from {remote}")

    # Optional: Validate auth token here
    # if config.AUTH_ENABLED:
    #     token = auth.get("token") if auth else None
    #     if not token or not validate_jwt(token):
    #         raise ConnectionRefusedError("Invalid authentication")

    await sio.emit("connected", {
        "sid": sid,
        "message": "Welcome to Varalokam! 🎨",
    }, to=sid)


@sio.event
async def disconnect(sid):
    """Handle client disconnection."""
    logger.info(f"✧ Client disconnected: {sid}")

    room = room_manager.get_player_room(sid)
    if room:
        player = room.players.get(sid)
        was_drawer = room.current_drawer_sid == sid

        # Remove player from room
        room, removed_player, room_deleted = room_manager.leave_room(sid)

        if room and not room_deleted:
            # Notify remaining players
            await sio.emit("room_player_left", {
                "playerName": removed_player.name if removed_player else "Unknown",
                "playerSid": sid,
                "disconnected": True,
                "newHostSid": room.host_sid,
                "playerCount": room.player_count,
                "players": [room.players[s].to_dict() for s in room.player_order if s in room.players],
            }, room=room.code)

            # If the drawer disconnected during an active game
            if was_drawer and room.status == "playing":
                if room.connected_count >= 2:
                    await handle_drawer_disconnect(sio, room)
                else:
                    # Not enough players — end the game
                    room.status = "waiting"
                    cleanup_room_timers(room.code)
                    await sio.emit("game_cancelled", {
                        "message": "Not enough players to continue",
                    }, room=room.code)

            # If too few players remain during a game
            elif room.status == "playing" and room.connected_count < 2:
                room.status = "waiting"
                cleanup_room_timers(room.code)
                await sio.emit("game_cancelled", {
                    "message": "Not enough players to continue",
                }, room=room.code)

        elif room_deleted:
            cleanup_room_timers(room.code)


# ── CORS Middleware for REST endpoints ─────────────────────
# (Socket.IO handles its own CORS internally, but aiohttp REST routes need this)
@web.middleware
async def cors_middleware(request, handler):
    """Add CORS headers to all HTTP responses."""
    # Handle preflight OPTIONS requests
    if request.method == "OPTIONS":
        response = web.Response()
    else:
        try:
            response = await handler(request)
        except web.HTTPException as ex:
            response = ex

    # Determine allowed origin
    origin = request.headers.get("Origin", "")
    allowed_origins = config.CORS_ORIGINS if not config.DEBUG else ["*"]

    if "*" in allowed_origins or origin in allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin or "*"
    elif allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = allowed_origins[0]

    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Max-Age"] = "3600"
    return response

app.middlewares.append(cors_middleware)


# ── REST API Endpoints (Health Check & Stats) ─────────────

async def health_check(request):
    """Health check endpoint for load balancer."""
    return web.json_response({
        "status": "healthy",
        "service": "varalokam",
        "rooms": room_manager.room_count,
        "players": room_manager.player_count,
    })


async def server_stats(request):
    """Server stats endpoint."""
    return web.json_response({
        "rooms": room_manager.room_count,
        "players": room_manager.player_count,
        "roomList": room_manager.get_room_list(),
    })


# ── Register HTTP Routes ─────────────────────────────────
app.router.add_get("/health", health_check)
app.router.add_get("/stats", server_stats)

# ── Serve static frontend files (optional) ───────────────
# If you want the backend to also serve the frontend:
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.router.add_static("/", FRONTEND_DIR, name="frontend")
    logger.info(f"Serving frontend from: {FRONTEND_DIR}")


# ── Main ──────────────────────────────────────────────────
def main():
    """Start the server."""
    logger.info("=" * 60)
    logger.info("  🎨  VARALOKAM — Draw & Guess Game Server")
    logger.info("=" * 60)
    logger.info(f"  Host:   {config.HOST}")
    logger.info(f"  Port:   {config.PORT}")
    logger.info(f"  Debug:  {config.DEBUG}")
    logger.info(f"  CORS:   {config.CORS_ORIGINS}")
    logger.info("=" * 60)

    web.run_app(
        app,
        host=config.HOST,
        port=config.PORT,
        print=None,  # We handle our own logging
    )


if __name__ == "__main__":
    main()
