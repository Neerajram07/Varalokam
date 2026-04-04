"""
Word Service — manages the word bank and word selection for the game.
"""

import json
import random
from pathlib import Path


# Load word bank from JSON file
_WORD_BANK_PATH = Path(__file__).parent.parent / "data" / "wordbank.json"
_word_bank: dict[str, list[str]] = {}


def _load_word_bank() -> dict[str, list[str]]:
    """Load the word bank from disk (lazy-loaded singleton)."""
    global _word_bank
    if not _word_bank:
        try:
            with open(_WORD_BANK_PATH, "r", encoding="utf-8") as f:
                _word_bank = json.load(f)
        except FileNotFoundError:
            # Fallback word bank if file is missing
            _word_bank = {
                "easy": [
                    "cat", "dog", "sun", "moon", "tree", "house", "car", "fish",
                    "bird", "star", "ball", "book", "door", "fire", "rain",
                    "cake", "hat", "shoe", "boat", "bell", "key", "bed",
                    "cup", "eye", "egg", "ice", "pen", "pig", "toy", "web",
                ],
                "medium": [
                    "guitar", "rocket", "castle", "dragon", "pirate", "wizard",
                    "zombie", "volcano", "unicorn", "penguin", "dolphin",
                    "rainbow", "diamond", "compass", "anchor", "bridge",
                    "candle", "desert", "forest", "garden", "island", "jungle",
                    "knight", "museum", "palace", "planet", "rabbit", "spider",
                    "tunnel", "wallet", "camera", "laptop", "mirror",
                ],
                "hard": [
                    "astronaut", "parachute", "telescope", "submarine", "earthquake",
                    "butterfly", "chandelier", "trampoline", "skateboard",
                    "lighthouse", "waterfall", "snowflake", "avalanche",
                    "chameleon", "porcupine", "scarecrow", "champagne",
                    "xylophone", "blueprint", "labyrinth", "nightmare",
                    "quicksand", "boomerang", "hamstring", "nostalgia",
                ],
            }
    return _word_bank


def get_word_choices(
    count: int = 3,
    difficulty: str = "mixed",
    custom_words: list[str] | None = None,
    use_custom_only: bool = False,
) -> list[str]:
    """
    Get random words for the drawer to choose from.

    Args:
        count: Number of word choices to present.
        difficulty: 'easy', 'medium', 'hard', or 'mixed'.
        custom_words: Optional custom word list from room settings.
        use_custom_only: If True, only use custom words.

    Returns:
        A list of `count` random words.
    """
    if use_custom_only and custom_words:
        pool = custom_words
    elif custom_words:
        # Mix custom words with standard words
        bank = _load_word_bank()
        pool = custom_words + bank.get("easy", []) + bank.get("medium", []) + bank.get("hard", [])
    else:
        bank = _load_word_bank()
        if difficulty == "mixed":
            # Pick one from each difficulty for variety
            choices = []
            for diff in ["easy", "medium", "hard"]:
                words = bank.get(diff, [])
                if words:
                    choices.append(random.choice(words))
            # Fill remaining if needed
            while len(choices) < count:
                all_words = bank.get("easy", []) + bank.get("medium", []) + bank.get("hard", [])
                choices.append(random.choice(all_words))
            return choices[:count]
        else:
            pool = bank.get(difficulty, bank.get("medium", []))

    if not pool:
        pool = ["drawing", "sketch", "paint"]  # absolute fallback

    return random.sample(pool, min(count, len(pool)))


def generate_hint(word: str, reveal_count: int) -> str:
    """
    Generate a hint string with some letters revealed.

    Args:
        word: The actual word.
        reveal_count: Number of letters to reveal.

    Returns:
        A hint string like "e _ e _ _ _ _ _"
    """
    if reveal_count <= 0:
        return " ".join("_" if c != " " else " " for c in word)

    # Determine which indices to reveal
    indices = list(range(len(word)))
    # Don't reveal spaces
    revealable = [i for i in indices if word[i] != " "]
    random.shuffle(revealable)
    revealed_indices = set(revealable[:reveal_count])

    hint_chars = []
    for i, char in enumerate(word):
        if char == " ":
            hint_chars.append("  ")  # double space for word gaps
        elif i in revealed_indices:
            hint_chars.append(char)
        else:
            hint_chars.append("_")

    return " ".join(hint_chars)


def check_guess(guess: str, word: str) -> bool:
    """
    Check if a guess matches the word (case-insensitive, trimmed).

    Args:
        guess: The player's guess message.
        word: The actual word.

    Returns:
        True if the guess is correct.
    """
    return guess.strip().lower() == word.strip().lower()


def is_close_guess(guess: str, word: str) -> bool:
    """
    Check if a guess is close to the word (for 'almost there' hints).
    Uses simple character overlap ratio.
    """
    g = guess.strip().lower()
    w = word.strip().lower()

    if len(g) != len(w):
        return False

    matches = sum(1 for a, b in zip(g, w) if a == b)
    return matches / len(w) >= 0.6 and matches != len(w)
