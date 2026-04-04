"""
Room model — represents a game room with players and settings.
"""

from __future__ import annotations

import random
import string
import time
from dataclasses import dataclass, field

from .player import Player


def _generate_room_code(length: int = 6) -> str:
    """Generate a random uppercase alphanumeric room code."""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


@dataclass
class Room:
    """A game room containing players and game configuration."""

    code: str = field(default_factory=_generate_room_code)
    host_sid: str = ""
    max_players: int = 8
    rounds_total: int = 3
    turn_duration: int = 80             # seconds per turn
    custom_words: list[str] = field(default_factory=list)
    use_custom_words_only: bool = False
    created_at: float = field(default_factory=time.time)

    # ── Player management ─────────────────────────────────
    players: dict[str, Player] = field(default_factory=dict)   # sid → Player
    player_order: list[str] = field(default_factory=list)      # ordered sids

    # ── Game state ────────────────────────────────────────
    status: str = "waiting"  # waiting | playing | finished
    current_round: int = 0
    current_drawer_index: int = 0
    current_word: str = ""
    word_choices: list[str] = field(default_factory=list)
    hint_revealed: str = ""
    turn_start_time: float = 0
    drawing_history: list[dict] = field(default_factory=list)

    # ── Properties ────────────────────────────────────────

    @property
    def player_count(self) -> int:
        return len(self.players)

    @property
    def is_full(self) -> bool:
        return self.player_count >= self.max_players

    @property
    def current_drawer_sid(self) -> str | None:
        if not self.player_order:
            return None
        idx = self.current_drawer_index % len(self.player_order)
        return self.player_order[idx]

    @property
    def current_drawer(self) -> Player | None:
        sid = self.current_drawer_sid
        return self.players.get(sid) if sid else None

    @property
    def all_guessed(self) -> bool:
        """Check if all non-drawer players have guessed."""
        for sid, player in self.players.items():
            if sid != self.current_drawer_sid and not player.has_guessed and player.is_connected:
                return False
        return True

    @property
    def connected_players(self) -> list[Player]:
        return [p for p in self.players.values() if p.is_connected]

    @property
    def connected_count(self) -> int:
        return len(self.connected_players)

    # ── Methods ───────────────────────────────────────────

    def add_player(self, player: Player) -> bool:
        """Add a player to the room. Returns False if full."""
        if self.is_full:
            return False
        self.players[player.sid] = player
        self.player_order.append(player.sid)
        if not self.host_sid:
            self.host_sid = player.sid
        return True

    def remove_player(self, sid: str) -> Player | None:
        """Remove a player entirely from the room."""
        player = self.players.pop(sid, None)
        if sid in self.player_order:
            # Adjust drawer index if needed
            removed_idx = self.player_order.index(sid)
            self.player_order.remove(sid)
            if self.current_drawer_index > removed_idx and self.current_drawer_index > 0:
                self.current_drawer_index -= 1
        # Transfer host
        if sid == self.host_sid and self.player_order:
            self.host_sid = self.player_order[0]
        return player

    def disconnect_player(self, sid: str) -> Player | None:
        """Mark a player as disconnected (for reconnection support)."""
        player = self.players.get(sid)
        if player:
            player.is_connected = False
        return player

    def get_scoreboard(self) -> list[dict]:
        """Get sorted scoreboard."""
        sorted_players = sorted(self.players.values(), key=lambda p: p.score, reverse=True)
        return [
            {"name": p.name, "score": p.score, "avatar": p.avatar, "sid": p.sid}
            for p in sorted_players
        ]

    def reset_for_new_game(self) -> None:
        """Reset room for a new game."""
        self.status = "waiting"
        self.current_round = 0
        self.current_drawer_index = 0
        self.current_word = ""
        self.word_choices = []
        self.hint_revealed = ""
        self.turn_start_time = 0
        self.drawing_history = []
        for player in self.players.values():
            player.reset_for_game()

    def reset_for_turn(self) -> None:
        """Reset per-turn state."""
        self.current_word = ""
        self.word_choices = []
        self.hint_revealed = ""
        self.turn_start_time = 0
        self.drawing_history = []
        for player in self.players.values():
            player.reset_for_turn()

    def to_dict(self) -> dict:
        """Serialize room state for sending to clients."""
        return {
            "code": self.code,
            "hostSid": self.host_sid,
            "maxPlayers": self.max_players,
            "roundsTotal": self.rounds_total,
            "turnDuration": self.turn_duration,
            "status": self.status,
            "currentRound": self.current_round,
            "currentDrawerSid": self.current_drawer_sid,
            "currentDrawerName": self.current_drawer.name if self.current_drawer else None,
            "hintRevealed": self.hint_revealed,
            "wordLength": len(self.current_word) if self.current_word else 0,
            "turnStartTime": self.turn_start_time,
            "players": [self.players[sid].to_dict() for sid in self.player_order if sid in self.players],
            "scoreboard": self.get_scoreboard(),
        }

    def to_dict_for_drawer(self) -> dict:
        """Serialize room state including the actual word (for drawer only)."""
        data = self.to_dict()
        data["currentWord"] = self.current_word
        return data
