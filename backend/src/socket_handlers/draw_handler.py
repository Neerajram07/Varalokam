"""
Draw Handler — Socket.IO events for real-time drawing relay.

Events handled:
  draw:stroke    → Relay drawing stroke data to all players in the room
  draw:clear     → Clear the canvas for all players
  draw:undo      → Undo last stroke
  draw:fill      → Fill canvas with a color

These events are HIGH FREQUENCY — they must be as lightweight as possible.
No database writes, no heavy processing. Just validate and broadcast.
"""

import logging
import socketio

from ..services.room_manager import room_manager

logger = logging.getLogger(__name__)


def register_draw_handlers(sio: socketio.AsyncServer) -> None:
    """Register all drawing-related socket event handlers."""

    @sio.event
    async def draw_stroke(sid, data):
        """
        Relay a drawing stroke to all other players in the room.

        Expected data (single point):
            {
                "x": float,        # X coordinate (0-1 normalized)
                "y": float,        # Y coordinate (0-1 normalized)
                "color": str,      # Hex color "#FF0000"
                "size": int,       # Brush size (1-50)
                "tool": str,       # "pen" | "eraser"
                "type": str,       # "start" | "move" | "end"
            }

        Or batch of points:
            {
                "points": [ {x, y} ... ],
                "color": str,
                "size": int,
                "tool": str,
            }

        Only the current drawer can send strokes.
        Broadcasts to all other players in the room (skip sender).
        """
        room = room_manager.get_player_room(sid)
        if not room:
            return

        # Only the current drawer can draw
        if room.current_drawer_sid != sid:
            return

        # Only during active drawing phase
        if room.status != "playing":
            return

        # Store in drawing history (for late joiners / replay)
        room.drawing_history.append(data)

        # Broadcast to all other players in the room — skip the drawer
        await sio.emit("draw_stroke", data, room=room.code, skip_sid=sid)

    @sio.event
    async def draw_clear(sid, data=None):
        """
        Clear the canvas for all players.
        Only the current drawer can clear.
        """
        room = room_manager.get_player_room(sid)
        if not room:
            return

        if room.current_drawer_sid != sid:
            return

        if room.status != "playing":
            return

        # Clear drawing history
        room.drawing_history = []

        await sio.emit("draw_clear", {}, room=room.code, skip_sid=sid)

    @sio.event
    async def draw_undo(sid, data=None):
        """
        Undo the last stroke.
        Only the current drawer can undo.

        The undo logic works by removing the last complete stroke
        from history and re-sending the entire history.
        """
        room = room_manager.get_player_room(sid)
        if not room:
            return

        if room.current_drawer_sid != sid:
            return

        if room.status != "playing":
            return

        # Remove strokes backwards until we find a "start" type
        while room.drawing_history:
            stroke = room.drawing_history.pop()
            if stroke.get("type") == "start":
                break

        # Send the full remaining history to re-render
        await sio.emit("draw_history", {
            "history": room.drawing_history,
        }, room=room.code, skip_sid=sid)

    @sio.event
    async def draw_fill(sid, data):
        """
        Fill the entire canvas with a color.
        Only the current drawer can fill.

        Expected data:
            { "color": str }
        """
        room = room_manager.get_player_room(sid)
        if not room:
            return

        if room.current_drawer_sid != sid:
            return

        if room.status != "playing":
            return

        color = data.get("color", "#FFFFFF")

        # Clear history and add fill event
        room.drawing_history = [{"type": "fill", "color": color}]

        await sio.emit("draw_fill", {"color": color}, room=room.code, skip_sid=sid)

    @sio.event
    async def draw_request_history(sid, data=None):
        """
        Request the current drawing history (for players who join mid-game
        or reconnect).
        """
        room = room_manager.get_player_room(sid)
        if not room:
            return

        await sio.emit("draw_history", {
            "history": room.drawing_history,
        }, to=sid)
