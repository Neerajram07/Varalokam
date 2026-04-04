"""
Room Handler — Socket.IO events for room management.

Events handled:
  room:create   → Creates a new room, returns room code
  room:join     → Joins an existing room by code
  room:leave    → Leaves the current room
  room:settings → Updates room settings (host only)
"""

import logging
import socketio

from ..services.room_manager import room_manager

logger = logging.getLogger(__name__)


def register_room_handlers(sio: socketio.AsyncServer) -> None:
    """Register all room-related socket event handlers."""

    @sio.event
    async def room_create(sid, data):
        """
        Create a new game room.

        Expected data:
            { "playerName": str, "avatar": str, "settings": { "maxPlayers": int, "rounds": int, "turnDuration": int } }

        Emits:
            room:created  → to creator with room state
        """
        player_name = data.get("playerName", "Player")
        avatar = data.get("avatar", "😀")
        settings = data.get("settings", {})

        room = room_manager.create_room(
            host_sid=sid,
            host_name=player_name,
            avatar=avatar,
            max_players=settings.get("maxPlayers", 8),
            rounds=settings.get("rounds", 3),
            turn_duration=settings.get("turnDuration", 80),
            custom_words=settings.get("customWords", []),
            use_custom_words_only=settings.get("useCustomWordsOnly", False),
        )

        # Join the Socket.IO room (for broadcasting)
        sio.enter_room(sid, room.code)

        await sio.emit("room_created", {
            "success": True,
            "room": room.to_dict(),
        }, to=sid)

        logger.info(f"[{room.code}] Room created by {player_name}")

    @sio.event
    async def room_join(sid, data):
        """
        Join an existing room by code.

        Expected data:
            { "roomCode": str, "playerName": str, "avatar": str }

        Emits:
            room:joined       → to joiner with room state
            room:playerJoined → to all others in room
        """
        room_code = data.get("roomCode", "").upper().strip()
        player_name = data.get("playerName", "Player")
        avatar = data.get("avatar", "😀")

        if not room_code:
            await sio.emit("room_error", {"message": "Room code is required"}, to=sid)
            return

        success, message, room = room_manager.join_room(
            code=room_code,
            sid=sid,
            name=player_name,
            avatar=avatar,
        )

        if not success:
            await sio.emit("room_error", {"message": message}, to=sid)
            return

        # Join the Socket.IO room
        sio.enter_room(sid, room.code)

        # Send full room state to the new player
        await sio.emit("room_joined", {
            "success": True,
            "room": room.to_dict(),
        }, to=sid)

        # Notify other players
        player = room.players[sid]
        await sio.emit("room_player_joined", {
            "player": player.to_dict(),
            "playerCount": room.player_count,
        }, room=room.code, skip_sid=sid)

        logger.info(f"[{room.code}] {player_name} joined ({room.player_count}/{room.max_players})")

    @sio.event
    async def room_leave(sid, data=None):
        """
        Leave the current room.

        Emits:
            room:left       → to the leaving player
            room:playerLeft → to all others in room
            room:hostChanged → if host left and was transferred
        """
        room, player, room_deleted = room_manager.leave_room(sid)

        if not room or not player:
            return

        # Leave the Socket.IO room
        sio.leave_room(sid, room.code)

        await sio.emit("room_left", {"success": True}, to=sid)

        if not room_deleted:
            # Notify remaining players
            await sio.emit("room_player_left", {
                "playerName": player.name,
                "playerSid": player.sid,
                "newHostSid": room.host_sid,
                "playerCount": room.player_count,
                "players": [room.players[s].to_dict() for s in room.player_order if s in room.players],
            }, room=room.code)

        logger.info(f"[{room.code}] {player.name} left")

    @sio.event
    async def room_settings(sid, data):
        """
        Update room settings (host only).

        Expected data:
            { "maxPlayers": int, "rounds": int, "turnDuration": int, "customWords": list }

        Emits:
            room:settingsUpdated → to all players in room
        """
        room = room_manager.get_player_room(sid)
        if not room:
            await sio.emit("room_error", {"message": "You are not in a room"}, to=sid)
            return

        if room.host_sid != sid:
            await sio.emit("room_error", {"message": "Only the host can change settings"}, to=sid)
            return

        if room.status != "waiting":
            await sio.emit("room_error", {"message": "Cannot change settings during a game"}, to=sid)
            return

        # Update settings
        if "maxPlayers" in data:
            room.max_players = max(2, min(12, data["maxPlayers"]))
        if "rounds" in data:
            room.rounds_total = max(1, min(10, data["rounds"]))
        if "turnDuration" in data:
            room.turn_duration = max(30, min(180, data["turnDuration"]))
        if "customWords" in data:
            room.custom_words = data["customWords"][:100]  # limit custom words
        if "useCustomWordsOnly" in data:
            room.use_custom_words_only = data["useCustomWordsOnly"]

        await sio.emit("room_settings_updated", {
            "room": room.to_dict(),
        }, room=room.code)

        logger.info(f"[{room.code}] Settings updated by host")

    @sio.event
    async def room_kick(sid, data):
        """
        Kick a player from the room (host only).

        Expected data:
            { "targetSid": str }
        """
        room = room_manager.get_player_room(sid)
        if not room or room.host_sid != sid:
            await sio.emit("room_error", {"message": "Only the host can kick players"}, to=sid)
            return

        target_sid = data.get("targetSid")
        if target_sid == sid:
            return  # Can't kick yourself

        target_player = room.players.get(target_sid)
        if not target_player:
            return

        # Remove from room
        room.remove_player(target_sid)
        room_manager._player_rooms.pop(target_sid, None)
        sio.leave_room(target_sid, room.code)

        # Notify kicked player
        await sio.emit("room_kicked", {"message": "You were kicked from the room"}, to=target_sid)

        # Notify room
        await sio.emit("room_player_left", {
            "playerName": target_player.name,
            "playerSid": target_sid,
            "kicked": True,
            "newHostSid": room.host_sid,
            "playerCount": room.player_count,
            "players": [room.players[s].to_dict() for s in room.player_order if s in room.players],
        }, room=room.code)

        logger.info(f"[{room.code}] {target_player.name} was kicked by host")
