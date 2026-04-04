"""
Chat Handler — Socket.IO events for chat messages and guess checking.

Events handled:
  chat:message → Player sends a chat message (which may be a guess)
"""

import logging
import time
import socketio

from ..services.room_manager import room_manager
from ..services.word_service import check_guess, is_close_guess
from ..services import score_service

logger = logging.getLogger(__name__)


def register_chat_handlers(sio: socketio.AsyncServer) -> None:
    """Register all chat-related socket event handlers."""

    @sio.event
    async def chat_message(sid, data):
        """
        Handle a chat message. If the game is active and the message
        matches the current word, it's treated as a correct guess.

        Expected data:
            { "message": str }

        Emits:
            chat:message     → Normal chat message to all
            game:correctGuess → If the guess is correct
            chat:system       → System messages ("Player guessed it!", "Close guess!")
        """
        room = room_manager.get_player_room(sid)
        if not room:
            return

        player = room.players.get(sid)
        if not player:
            return

        message = data.get("message", "").strip()
        if not message:
            return

        # Limit message length
        message = message[:200]

        # ── If the game is active, check for guesses ──────
        if room.status == "playing" and room.current_word:
            # The drawer cannot guess
            if sid == room.current_drawer_sid:
                # Drawer's messages are just normal chat
                await sio.emit("chat_message", {
                    "playerName": player.name,
                    "message": message,
                    "type": "chat",
                    "avatar": player.avatar,
                }, room=room.code)
                return

            # Already guessed players can chat but not guess again
            if player.has_guessed:
                # Only show to other players who have also guessed (and the drawer)
                for p_sid, p in room.players.items():
                    if p.has_guessed or p_sid == room.current_drawer_sid:
                        await sio.emit("chat_message", {
                            "playerName": player.name,
                            "message": message,
                            "type": "guessed_chat",
                            "avatar": player.avatar,
                        }, to=p_sid)
                return

            # ── Check if it's a correct guess ─────────────
            if check_guess(message, room.current_word):
                await _handle_correct_guess(sio, room, player, sid)
                return

            # ── Check if it's a close guess ───────────────
            if is_close_guess(message, room.current_word):
                await sio.emit("chat_system", {
                    "message": f"{player.name} is close!",
                    "type": "close_guess",
                }, room=room.code)
                # Don't show the actual message (it contains a close word)
                # Instead show a censored version
                await sio.emit("chat_message", {
                    "playerName": player.name,
                    "message": "🤔 ...",
                    "type": "close",
                    "avatar": player.avatar,
                }, room=room.code)
                return

        # ── Normal chat message ───────────────────────────
        await sio.emit("chat_message", {
            "playerName": player.name,
            "message": message,
            "type": "chat",
            "avatar": player.avatar,
        }, room=room.code)


async def _handle_correct_guess(sio, room, player, sid):
    """Handle a player guessing the word correctly."""
    now = time.time()
    player.has_guessed = True
    player.guess_time = now

    # Count how many have guessed before this player
    guess_order = sum(
        1 for p in room.players.values()
        if p.has_guessed and p.sid != sid and p.sid != room.current_drawer_sid
    )

    # Calculate time remaining
    elapsed = now - room.turn_start_time
    time_remaining = max(0, room.turn_duration - elapsed)

    # Calculate score
    total_guessers = room.player_count - 1  # exclude drawer
    guesser_score = score_service.calculate_guesser_score(
        time_remaining=time_remaining,
        total_time=room.turn_duration,
        guess_order=guess_order,
        total_players=total_guessers,
    )

    player.score += guesser_score

    # Update drawer's score
    drawer = room.current_drawer
    if drawer:
        correct_count = sum(
            1 for p in room.players.values()
            if p.has_guessed and p.sid != room.current_drawer_sid
        )
        drawer_score = score_service.calculate_drawer_score(correct_count, total_guessers)
        # Only set (not accumulate) — will finalize at turn end
        # For now just track the running total

    # Notify everyone
    await sio.emit("game_correct_guess", {
        "playerName": player.name,
        "playerSid": sid,
        "score": guesser_score,
        "totalScore": player.score,
        "guessOrder": guess_order + 1,
    }, room=room.code)

    # System message
    await sio.emit("chat_system", {
        "message": f"🎉 {player.name} guessed the word!",
        "type": "correct_guess",
    }, room=room.code)

    # Check if all players have guessed → end turn early
    if room.all_guessed:
        # Import here to avoid circular imports
        from .game_handler import end_turn
        await end_turn(sio, room, reason="all_guessed")

    logger.info(f"[{room.code}] {player.name} guessed correctly (+{guesser_score}pts)")
