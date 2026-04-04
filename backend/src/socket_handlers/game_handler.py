"""
Game Handler — the core game loop and state machine.

Manages the full lifecycle of a game:
  Start → Word Selection → Drawing/Guessing → Turn Reveal → ... → Game Over

Events handled:
  game:start         → Host starts the game
  game:wordSelected  → Drawer picks a word
  game:playAgain     → Start a new game in the same room

Timers:
  - Word selection timeout (15s)
  - Turn timer (configurable, default 80s)
  - Hint reveal timer (every 20s)
  - Turn reveal pause (5s)
"""

import asyncio
import logging
import time
import socketio

from ..config import config
from ..models.game import GameState
from ..services.room_manager import room_manager
from ..services.word_service import get_word_choices, generate_hint
from ..services import score_service

logger = logging.getLogger(__name__)

# Track active timers so we can cancel them
_active_timers: dict[str, dict[str, asyncio.Task]] = {}  # room_code → { timer_name → Task }


def _cancel_room_timers(room_code: str) -> None:
    """Cancel all active timers for a room."""
    timers = _active_timers.pop(room_code, {})
    for name, task in timers.items():
        if not task.done():
            task.cancel()
            logger.debug(f"[{room_code}] Cancelled timer: {name}")


def _set_timer(room_code: str, name: str, coro) -> None:
    """Set a named timer for a room, cancelling any existing timer with the same name."""
    if room_code not in _active_timers:
        _active_timers[room_code] = {}

    # Cancel existing timer with same name
    existing = _active_timers[room_code].get(name)
    if existing and not existing.done():
        existing.cancel()

    _active_timers[room_code][name] = asyncio.create_task(coro)


def register_game_handlers(sio: socketio.AsyncServer) -> None:
    """Register all game-related socket event handlers."""

    @sio.event
    async def game_start(sid, data=None):
        """
        Start the game. Only the host can start, and minimum 2 players required.
        """
        room = room_manager.get_player_room(sid)
        if not room:
            await sio.emit("game_error", {"message": "You are not in a room"}, to=sid)
            return

        if room.host_sid != sid:
            await sio.emit("game_error", {"message": "Only the host can start the game"}, to=sid)
            return

        if room.connected_count < 2:
            await sio.emit("game_error", {"message": "Need at least 2 players to start"}, to=sid)
            return

        if room.status != "waiting":
            await sio.emit("game_error", {"message": "Game is already in progress"}, to=sid)
            return

        logger.info(f"[{room.code}] Game starting with {room.player_count} players")

        # Initialize game state
        room.status = "playing"
        room.current_round = 1
        room.current_drawer_index = 0

        for player in room.players.values():
            player.reset_for_game()

        # Notify all players
        await sio.emit("game_started", {
            "round": room.current_round,
            "totalRounds": room.rounds_total,
            "players": [room.players[s].to_dict() for s in room.player_order if s in room.players],
        }, room=room.code)

        # Start first turn
        await start_word_selection(sio, room)

    @sio.event
    async def game_word_selected(sid, data):
        """
        Drawer selects a word from the choices.

        Expected data:
            { "word": str }
        """
        room = room_manager.get_player_room(sid)
        if not room:
            return

        if room.current_drawer_sid != sid:
            await sio.emit("game_error", {"message": "You are not the drawer"}, to=sid)
            return

        word = data.get("word", "")
        if word not in room.word_choices:
            await sio.emit("game_error", {"message": "Invalid word selection"}, to=sid)
            return

        # Cancel word selection timer
        timers = _active_timers.get(room.code, {})
        word_timer = timers.get("word_selection")
        if word_timer and not word_timer.done():
            word_timer.cancel()

        await start_drawing_phase(sio, room, word)

    @sio.event
    async def game_play_again(sid, data=None):
        """
        Start a new game in the same room. Only host can trigger.
        """
        room = room_manager.get_player_room(sid)
        if not room:
            return

        if room.host_sid != sid:
            await sio.emit("game_error", {"message": "Only the host can restart"}, to=sid)
            return

        _cancel_room_timers(room.code)
        room.reset_for_new_game()

        await sio.emit("game_reset", {
            "room": room.to_dict(),
        }, room=room.code)

        logger.info(f"[{room.code}] Game reset, back to lobby")


async def start_word_selection(sio: socketio.AsyncServer, room) -> None:
    """Present word choices to the current drawer."""
    room.reset_for_turn()

    drawer = room.current_drawer
    if not drawer:
        logger.error(f"[{room.code}] No drawer found!")
        return

    # Get word choices
    words = get_word_choices(
        count=config.WORD_CHOICE_COUNT,
        custom_words=room.custom_words,
        use_custom_only=room.use_custom_words_only,
    )
    room.word_choices = words

    # Send choices to the drawer only
    await sio.emit("game_word_choices", {
        "words": words,
        "timeout": config.WORD_CHOICE_TIMEOUT,
    }, to=drawer.sid)

    # Tell everyone else who the drawer is
    await sio.emit("game_choosing_word", {
        "drawerName": drawer.name,
        "drawerSid": drawer.sid,
        "round": room.current_round,
        "totalRounds": room.rounds_total,
    }, room=room.code, skip_sid=drawer.sid)

    logger.info(f"[{room.code}] {drawer.name} is choosing a word")

    # Set timeout — auto-pick a word if drawer doesn't choose
    async def word_selection_timeout():
        await asyncio.sleep(config.WORD_CHOICE_TIMEOUT)
        # Auto-select a random word
        if room.word_choices and not room.current_word:
            import random
            auto_word = random.choice(room.word_choices)
            logger.info(f"[{room.code}] Auto-selected word: {auto_word}")
            await start_drawing_phase(sio, room, auto_word)

    _set_timer(room.code, "word_selection", word_selection_timeout())


async def start_drawing_phase(sio: socketio.AsyncServer, room, word: str) -> None:
    """Start the active drawing and guessing phase."""
    room.current_word = word
    room.word_choices = []
    room.turn_start_time = time.time()
    room.drawing_history = []

    # Generate initial hint (all underscores)
    room.hint_revealed = generate_hint(word, 0)

    drawer = room.current_drawer

    # Notify the drawer — they see the actual word
    await sio.emit("game_turn_start", {
        "isDrawer": True,
        "word": word,
        "wordLength": len(word),
        "hint": room.hint_revealed,
        "duration": room.turn_duration,
        "drawerName": drawer.name,
        "drawerSid": drawer.sid,
        "round": room.current_round,
    }, to=drawer.sid)

    # Notify all guessers — they see the hint
    await sio.emit("game_turn_start", {
        "isDrawer": False,
        "wordLength": len(word),
        "hint": room.hint_revealed,
        "duration": room.turn_duration,
        "drawerName": drawer.name,
        "drawerSid": drawer.sid,
        "round": room.current_round,
    }, room=room.code, skip_sid=drawer.sid)

    logger.info(f"[{room.code}] Drawing phase started. Word: {word}")

    # Start the turn timer
    async def turn_timer():
        hints_given = 0
        total_hints = max(1, len(word) // 2)  # reveal up to half the letters
        hint_interval = room.turn_duration / (total_hints + 1)

        elapsed = 0
        while elapsed < room.turn_duration:
            await asyncio.sleep(1)
            elapsed += 1

            # Send timer tick every 5 seconds
            if elapsed % 5 == 0:
                remaining = room.turn_duration - elapsed
                await sio.emit("game_timer", {
                    "remaining": remaining,
                    "total": room.turn_duration,
                }, room=room.code)

            # Reveal hints at intervals
            if elapsed > 0 and elapsed % hint_interval < 1 and hints_given < total_hints:
                hints_given += 1
                room.hint_revealed = generate_hint(word, hints_given)
                await sio.emit("game_hint", {
                    "hint": room.hint_revealed,
                    "hintsGiven": hints_given,
                }, room=room.code)

        # Time's up!
        await end_turn(sio, room, reason="timeout")

    _set_timer(room.code, "turn_timer", turn_timer())


async def end_turn(sio: socketio.AsyncServer, room, reason: str = "timeout") -> None:
    """
    End the current turn, reveal the word, and calculate scores.

    reason: "timeout" | "all_guessed" | "drawer_left"
    """
    # Cancel timers
    timers = _active_timers.get(room.code, {})
    for name in ["turn_timer", "hint_timer"]:
        timer = timers.get(name)
        if timer and not timer.done():
            timer.cancel()

    # Calculate final drawer score
    drawer = room.current_drawer
    if drawer:
        correct_count = sum(
            1 for p in room.players.values()
            if p.has_guessed and p.sid != room.current_drawer_sid
        )
        total_guessers = room.player_count - 1
        drawer_bonus = score_service.calculate_drawer_score(correct_count, total_guessers)
        drawer.score += drawer_bonus

    # Reveal the word
    await sio.emit("game_turn_end", {
        "word": room.current_word,
        "reason": reason,
        "scoreboard": room.get_scoreboard(),
        "drawerBonus": drawer_bonus if drawer else 0,
    }, room=room.code)

    logger.info(f"[{room.code}] Turn ended ({reason}). Word was: {room.current_word}")

    # Brief pause before next turn
    async def next_turn_delay():
        await asyncio.sleep(5)
        await advance_to_next_turn(sio, room)

    _set_timer(room.code, "next_turn", next_turn_delay())


async def advance_to_next_turn(sio: socketio.AsyncServer, room) -> None:
    """Advance to the next drawer or next round or game over."""

    # Move to next drawer
    room.current_drawer_index += 1

    # Check if we've gone through all players this round
    if room.current_drawer_index >= len(room.player_order):
        room.current_drawer_index = 0
        room.current_round += 1

        # Check if game is over
        if room.current_round > room.rounds_total:
            await end_game(sio, room)
            return

        # Notify round change
        await sio.emit("game_round_change", {
            "round": room.current_round,
            "totalRounds": room.rounds_total,
            "scoreboard": room.get_scoreboard(),
        }, room=room.code)

        logger.info(f"[{room.code}] Round {room.current_round} starting")

    # Start word selection for next drawer
    await start_word_selection(sio, room)


async def end_game(sio: socketio.AsyncServer, room) -> None:
    """End the game and show final results."""
    _cancel_room_timers(room.code)

    scoreboard = room.get_scoreboard()
    winner = scoreboard[0] if scoreboard else None

    room.status = "waiting"

    await sio.emit("game_over", {
        "scoreboard": scoreboard,
        "winner": winner,
    }, room=room.code)

    logger.info(
        f"[{room.code}] Game over! Winner: {winner['name'] if winner else 'Nobody'} "
        f"({winner['score'] if winner else 0}pts)"
    )

    # Optionally save stats to DynamoDB
    # from ..services.dynamo_service import dynamo_service
    # for player_data in scoreboard:
    #     await dynamo_service.update_user_stats(...)


async def handle_drawer_disconnect(sio: socketio.AsyncServer, room) -> None:
    """Handle the current drawer disconnecting mid-turn."""
    logger.info(f"[{room.code}] Drawer disconnected, ending turn")
    await end_turn(sio, room, reason="drawer_left")


def cleanup_room_timers(room_code: str) -> None:
    """Clean up all timers when a room is deleted."""
    _cancel_room_timers(room_code)
