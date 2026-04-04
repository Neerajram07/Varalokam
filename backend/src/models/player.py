"""
Player model — represents a connected player in a game room.
"""

from dataclasses import dataclass, field
import time


@dataclass
class Player:
    """A player connected to a game room."""

    sid: str                          # Socket.IO session ID
    name: str                         # Display name
    avatar: str = "😀"                # Emoji avatar
    score: int = 0                    # Current game score
    has_guessed: bool = False         # Has guessed the current word?
    is_connected: bool = True         # Still connected?
    guess_time: float | None = None   # When they guessed correctly (epoch)
    joined_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        """Serialize player for sending to clients."""
        return {
            "sid": self.sid,
            "name": self.name,
            "avatar": self.avatar,
            "score": self.score,
            "hasGuessed": self.has_guessed,
            "isConnected": self.is_connected,
        }

    def reset_for_turn(self) -> None:
        """Reset per-turn state."""
        self.has_guessed = False
        self.guess_time = None

    def reset_for_game(self) -> None:
        """Reset all game state for a new game."""
        self.score = 0
        self.has_guessed = False
        self.guess_time = None
