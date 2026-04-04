"""
Game state machine — manages game flow and transitions.

States:
  WAITING        → Players in lobby, waiting to start
  WORD_SELECTION  → Current drawer is choosing a word
  DRAWING        → Active drawing & guessing phase
  TURN_REVEAL    → Word revealed, brief pause
  ROUND_END      → Round scores shown
  GAME_OVER      → Final scoreboard
"""

from enum import Enum


class GameState(str, Enum):
    WAITING = "waiting"
    WORD_SELECTION = "word_selection"
    DRAWING = "drawing"
    TURN_REVEAL = "turn_reveal"
    ROUND_END = "round_end"
    GAME_OVER = "game_over"


# Valid state transitions
TRANSITIONS: dict[GameState, list[GameState]] = {
    GameState.WAITING: [GameState.WORD_SELECTION],
    GameState.WORD_SELECTION: [GameState.DRAWING, GameState.WAITING],
    GameState.DRAWING: [GameState.TURN_REVEAL],
    GameState.TURN_REVEAL: [GameState.WORD_SELECTION, GameState.ROUND_END],
    GameState.ROUND_END: [GameState.WORD_SELECTION, GameState.GAME_OVER],
    GameState.GAME_OVER: [GameState.WAITING],
}


def can_transition(current: GameState, target: GameState) -> bool:
    """Check if a state transition is valid."""
    return target in TRANSITIONS.get(current, [])


def validate_transition(current: GameState, target: GameState) -> None:
    """Validate and raise if transition is not allowed."""
    if not can_transition(current, target):
        raise ValueError(
            f"Invalid state transition: {current.value} → {target.value}. "
            f"Allowed: {[s.value for s in TRANSITIONS.get(current, [])]}"
        )
