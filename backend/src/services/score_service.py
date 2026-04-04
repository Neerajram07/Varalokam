"""
Score Service — handles point calculations for guessers and drawers.
"""

import math


def calculate_guesser_score(
    time_remaining: float,
    total_time: float,
    guess_order: int,
    total_players: int,
) -> int:
    """
    Calculate points for a player who guessed correctly.

    Scoring factors:
    - Speed: Faster guesses earn more points (500 max, 100 min)
    - Order bonus: First guesser gets a small bonus

    Args:
        time_remaining: Seconds left when guessed.
        total_time: Total turn duration in seconds.
        guess_order: Which number guesser (0-indexed, 0 = first).
        total_players: Total players in the room (excluding drawer).

    Returns:
        Score points (integer).
    """
    if total_time <= 0:
        return 100

    # Base score: time-based (100 to 500)
    max_points = 500
    min_points = 100
    time_ratio = max(0.0, min(1.0, time_remaining / total_time))
    base_score = min_points + (max_points - min_points) * time_ratio

    # Order bonus: first guesser gets +50, second +30, third +10
    order_bonus = max(0, 50 - (guess_order * 20))

    return round(base_score + order_bonus)


def calculate_drawer_score(
    num_correct_guessers: int,
    total_guessers: int,
) -> int:
    """
    Calculate points for the drawer based on how many people guessed.

    Args:
        num_correct_guessers: Number of players who guessed correctly.
        total_guessers: Total non-drawer players.

    Returns:
        Score points (integer).
    """
    if total_guessers <= 0 or num_correct_guessers <= 0:
        return 0

    # Base: 50 per correct guesser
    base = num_correct_guessers * 50

    # Bonus if everyone guessed
    if num_correct_guessers == total_guessers:
        base += 100

    # Percentage bonus (if more than half guessed)
    ratio = num_correct_guessers / total_guessers
    if ratio > 0.5:
        base = round(base * 1.2)

    return min(base, 500)  # Cap at 500


def calculate_hint_penalty(hints_given: int) -> float:
    """
    Score multiplier based on number of hints given.
    More hints = lower score multiplier for guesser.
    """
    if hints_given <= 0:
        return 1.0
    return max(0.5, 1.0 - (hints_given * 0.15))
