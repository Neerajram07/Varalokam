"""
Room Handler — Socket.IO events for room management.

Events handled:
  room:create     → Creates a new room, returns room code
  room:join       → Joins an existing room by code
  room:leave      → Leaves the current room
  room:settings   → Updates room settings (host only)
  quick_play      → Matchmaking: find or create a public room
"""

import asyncio
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

    # ── Quick Play / Play Online ───────────────────────────

    # Track auto-start countdown timers for public rooms
    _auto_start_timers: dict[str, asyncio.Task] = {}

    @sio.event
    async def quick_play(sid, data):
        """
        Quick Play / Play Online — matchmaking without room codes.

        The player clicks "Play Online" and is automatically placed
        into an available public room, or a new one is created.

        When enough players join (default 3), a 10-second countdown
        starts and the game auto-starts.

        Expected data:
            { "playerName": str, "avatar": str }

        Emits:
            quick_play_joined   → to the player with room state
            room_player_joined  → to others in the room
            quick_play_countdown → countdown before auto-start
            game_started         → when countdown finishes
        """
        player_name = data.get("playerName", "Player")
        avatar = data.get("avatar", "😀")

        # Use matchmaking to find or create a public room
        is_new_room, message, room = room_manager.quick_play(
            sid=sid,
            name=player_name,
            avatar=avatar,
        )

        if not room:
            await sio.emit("room_error", {"message": message}, to=sid)
            return

        # Join the Socket.IO room for broadcasting
        sio.enter_room(sid, room.code)

        # Send room state to the new player
        player = room.players[sid]
        await sio.emit("quick_play_joined", {
            "success": True,
            "isNewRoom": is_new_room,
            "room": room.to_dict(),
            "message": f"Waiting for players... ({room.player_count}/{room.min_players_to_start} needed to start)",
        }, to=sid)

        # Notify other players in the room
        if not is_new_room:
            await sio.emit("room_player_joined", {
                "player": player.to_dict(),
                "playerCount": room.player_count,
            }, room=room.code, skip_sid=sid)

        logger.info(f"[QUICKPLAY][{room.code}] {player_name} joined ({room.player_count} players)")

        # ── Auto-start logic ──────────────────────────────
        if (
            room.auto_start
            and room.status == "waiting"
            and room.player_count >= room.min_players_to_start
            and room.code not in _auto_start_timers
        ):
            # Start countdown!
            logger.info(f"[QUICKPLAY][{room.code}] Auto-start countdown ({room.auto_start_countdown}s)")

            async def auto_start_countdown():
                try:
                    countdown = room.auto_start_countdown

                    # Notify everyone about the countdown
                    await sio.emit("quick_play_countdown", {
                        "seconds": countdown,
                        "message": f"Game starting in {countdown} seconds!",
                    }, room=room.code)

                    # Tick down
                    for remaining in range(countdown, 0, -1):
                        await asyncio.sleep(1)

                        # Check if room still valid and has enough players
                        if (
                            room.status != "waiting"
                            or room.player_count < 2
                        ):
                            await sio.emit("quick_play_countdown_cancelled", {
                                "message": "Not enough players, waiting for more...",
                            }, room=room.code)
                            return

                        # Send countdown tick every second
                        await sio.emit("quick_play_countdown", {
                            "seconds": remaining - 1,
                            "message": f"Game starting in {remaining - 1} seconds!" if remaining > 1 else "Starting now!",
                        }, room=room.code)

                    # Auto-start the game!
                    if room.status == "waiting" and room.player_count >= 2:
                        room.status = "playing"
                        room.current_round = 1
                        room.current_drawer_index = 0

                        for p in room.players.values():
                            p.reset_for_game()

                        await sio.emit("game_started", {
                            "round": room.current_round,
                            "totalRounds": room.rounds_total,
                            "players": [room.players[s].to_dict() for s in room.player_order if s in room.players],
                            "autoStarted": True,
                        }, room=room.code)

                        # Import here to avoid circular dependency
                        from .game_handler import start_word_selection
                        await start_word_selection(sio, room)

                        logger.info(f"[QUICKPLAY][{room.code}] Game auto-started with {room.player_count} players!")

                except asyncio.CancelledError:
                    pass
                finally:
                    _auto_start_timers.pop(room.code, None)

            _auto_start_timers[room.code] = asyncio.create_task(auto_start_countdown())

        elif (
            room.auto_start
            and room.status == "waiting"
            and room.player_count < room.min_players_to_start
        ):
            # Not enough players yet — send waiting message
            needed = room.min_players_to_start - room.player_count
            await sio.emit("quick_play_waiting", {
                "playerCount": room.player_count,
                "needed": needed,
                "message": f"Waiting for {needed} more player{'s' if needed > 1 else ''}...",
            }, room=room.code)
