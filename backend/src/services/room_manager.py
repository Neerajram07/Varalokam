"""
Room Manager Service — centralized in-memory room management.

This is the single source of truth for all active game rooms.
For a single-server setup this stores rooms in memory.
When scaling with Redis, this would be replaced with Redis-backed state.
"""

from __future__ import annotations

import logging
from typing import Optional

from ..models.player import Player
from ..models.room import Room

logger = logging.getLogger(__name__)


class RoomManager:
    """Manages all active game rooms in memory."""

    def __init__(self):
        self._rooms: dict[str, Room] = {}          # code → Room
        self._player_rooms: dict[str, str] = {}    # sid → room_code

    # ── Room CRUD ─────────────────────────────────────────

    def create_room(self, host_sid: str, host_name: str, **settings) -> Room:
        """Create a new room and add the host as the first player."""
        room = Room(
            host_sid=host_sid,
            max_players=settings.get("max_players", 8),
            rounds_total=settings.get("rounds", 3),
            turn_duration=settings.get("turn_duration", 80),
            custom_words=settings.get("custom_words", []),
            use_custom_words_only=settings.get("use_custom_words_only", False),
        )

        # Ensure unique code
        while room.code in self._rooms:
            room.code = room._generate_room_code()

        host = Player(sid=host_sid, name=host_name, avatar=settings.get("avatar", "😀"))
        room.add_player(host)

        self._rooms[room.code] = room
        self._player_rooms[host_sid] = room.code

        logger.info(f"Room {room.code} created by {host_name} ({host_sid})")
        return room

    def get_room(self, code: str) -> Optional[Room]:
        """Get a room by its code."""
        return self._rooms.get(code.upper())

    def get_player_room(self, sid: str) -> Optional[Room]:
        """Get the room a player is currently in."""
        code = self._player_rooms.get(sid)
        return self._rooms.get(code) if code else None

    def join_room(self, code: str, sid: str, name: str, avatar: str = "😀") -> tuple[bool, str, Optional[Room]]:
        """
        Join an existing room.

        Returns:
            (success, message, room)
        """
        room = self.get_room(code.upper())
        if not room:
            return False, "Room not found", None

        if room.is_full:
            return False, "Room is full", None

        if room.status != "waiting":
            return False, "Game already in progress", None

        # Check for duplicate names
        for player in room.players.values():
            if player.name.lower() == name.lower():
                return False, "Name already taken in this room", None

        player = Player(sid=sid, name=name, avatar=avatar)
        room.add_player(player)
        self._player_rooms[sid] = room.code

        logger.info(f"Player {name} ({sid}) joined room {room.code}")
        return True, "Joined successfully", room

    def leave_room(self, sid: str) -> tuple[Optional[Room], Optional[Player], bool]:
        """
        Remove a player from their current room.

        Returns:
            (room, removed_player, room_was_deleted)
        """
        code = self._player_rooms.pop(sid, None)
        if not code:
            return None, None, False

        room = self._rooms.get(code)
        if not room:
            return None, None, False

        player = room.remove_player(sid)

        # Delete room if empty
        if room.player_count == 0:
            del self._rooms[code]
            logger.info(f"Room {code} deleted (empty)")
            return room, player, True

        logger.info(f"Player {player.name if player else sid} left room {code}")
        return room, player, False

    def delete_room(self, code: str) -> None:
        """Force-delete a room and clean up player mappings."""
        room = self._rooms.pop(code, None)
        if room:
            for sid in list(room.players.keys()):
                self._player_rooms.pop(sid, None)
            logger.info(f"Room {code} force-deleted")

    # ── Stats ─────────────────────────────────────────────

    @property
    def room_count(self) -> int:
        return len(self._rooms)

    @property
    def player_count(self) -> int:
        return len(self._player_rooms)

    def get_room_list(self) -> list[dict]:
        """Get a summary of all rooms (for lobby browser)."""
        return [
            {
                "code": room.code,
                "playerCount": room.player_count,
                "maxPlayers": room.max_players,
                "status": room.status,
                "hostName": room.players.get(room.host_sid, Player(sid="", name="Unknown")).name,
            }
            for room in self._rooms.values()
        ]

    # ── Quick Play / Matchmaking ──────────────────────────

    def find_public_room(self) -> Optional[Room]:
        """
        Find an available public room for quick play matchmaking.
        Returns the best room (most players but not full, still waiting).
        """
        candidates = [
            room for room in self._rooms.values()
            if room.is_public
            and room.status == "waiting"
            and not room.is_full
        ]

        if not candidates:
            return None

        # Pick the room with the most players (so games start faster)
        candidates.sort(key=lambda r: r.player_count, reverse=True)
        return candidates[0]

    def quick_play(self, sid: str, name: str, avatar: str = "😀") -> tuple[bool, str, Optional[Room]]:
        """
        Quick play matchmaking — find or create a public room.

        Logic:
        1. Look for an existing public room that's waiting and not full
        2. If found → join it
        3. If not found → create a new public room

        Returns:
            (is_new_room, message, room)
        """
        # Check if player is already in a room
        if sid in self._player_rooms:
            existing = self.get_player_room(sid)
            if existing:
                return False, "You are already in a room. Leave first.", None

        # Try to find an existing public room
        room = self.find_public_room()

        if room:
            # Join existing public room
            # Check for duplicate names — append number if needed
            original_name = name
            counter = 1
            while any(p.name.lower() == name.lower() for p in room.players.values()):
                counter += 1
                name = f"{original_name}{counter}"

            player = Player(sid=sid, name=name, avatar=avatar)
            room.add_player(player)
            self._player_rooms[sid] = room.code

            logger.info(f"[QUICKPLAY] {name} ({sid}) joined public room {room.code} ({room.player_count}/{room.max_players})")
            return False, "Joined public room", room

        else:
            # Create a new public room
            room = Room(
                host_sid=sid,
                max_players=8,
                rounds_total=3,
                turn_duration=80,
                is_public=True,
                auto_start=True,
                min_players_to_start=3,
                auto_start_countdown=10,
            )

            # Ensure unique code
            while room.code in self._rooms:
                from .room import _generate_room_code
                room.code = _generate_room_code()

            player = Player(sid=sid, name=name, avatar=avatar)
            room.add_player(player)

            self._rooms[room.code] = room
            self._player_rooms[sid] = room.code

            logger.info(f"[QUICKPLAY] {name} ({sid}) created new public room {room.code}")
            return True, "Created new public room", room


# Singleton instance
room_manager = RoomManager()
