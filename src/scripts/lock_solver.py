from concurrent.futures import ProcessPoolExecutor
from itertools import product
import os
import random

MAX_GUESSES = 12
MAX_OPTIONS = 12
CODE_LENGTH = 4
GREEDY_THRESHOLD = 1000  # When to switch from minimax to greedy first-pick for speed

def get_code(code_length: int = CODE_LENGTH, max_options: int = MAX_OPTIONS) -> list[int]:
    return [random.randint(1, max_options) for _ in range(code_length)]

def score(guess: tuple, candidate: tuple) -> tuple:
    """Returns (correct_position_count, correct_number_wrong_position_count)."""
    correct_pos = sum(g == c for g, c in zip(guess, candidate))
    correct_num = sum(min(guess.count(n), candidate.count(n)) for n in set(guess))
    return correct_pos, correct_num - correct_pos

# Module-level state shared with worker processes via pool initializer.
_worker_remaining: list = []


def _init_worker(remaining: list) -> None:
    """Initialise each worker process with a shared copy of the candidate list."""
    global _worker_remaining
    _worker_remaining = remaining


def _score_candidate(g: tuple) -> int:
    """Return the worst-case bucket size for candidate *g* against the shared pool."""
    buckets: dict = {}
    for c in _worker_remaining:
        fb = score(g, c)
        buckets[fb] = buckets.get(fb, 0) + 1
    return max(buckets.values())


def _minimax_guess(remaining: list) -> tuple:
    """Pick the candidate that minimises the largest feedback bucket (minimax).

    The per-candidate scoring is distributed across worker processes.  Each
    worker receives *remaining* once via the pool initializer so it is not
    re-serialised on every task call.
    """
    n_workers = min(os.cpu_count() or 1, len(remaining))
    chunksize = max(1, len(remaining) // n_workers)
    with ProcessPoolExecutor(
        max_workers=n_workers,
        initializer=_init_worker,
        initargs=(remaining,),
    ) as executor:
        scores = list(executor.map(_score_candidate, remaining, chunksize=chunksize))
    return remaining[scores.index(min(scores))]

def solve_lock(code: list, max_guesses: int = MAX_GUESSES) -> list:
    """
    Solves the lock using constraint elimination + minimax selection.
    After each guess the feedback is used to discard any candidate that
    could not have produced that same feedback, shrinking the search space
    each round.  When the candidate pool is small enough, minimax picks the
    next guess to minimise the worst-case remaining set size.
    """
    print(f"\n=========================================")
    print(f"Starting solver | code length: {len(code)}, options: 1-{MAX_OPTIONS}")

    code_tuple = tuple(code)
    code_len = len(code)

    all_codes = list(product(range(1, MAX_OPTIONS + 1), repeat=code_len))
    remaining = all_codes.copy()

    # Spread first guess (e.g. [1,2,3,4]) probes distinct values, eliminating more candidates
    guess = tuple((i % MAX_OPTIONS) + 1 for i in range(code_len))

    for attempt in range(1, max_guesses + 1):
        print(f"\nGuess #{attempt}: {list(guess)}")
        feedback = score(guess, code_tuple)
        print(f"  Correct position: {feedback[0]}  |  Wrong position: {feedback[1]}")

        if feedback[0] == code_len:
            print(f"\nSolved in {attempt} guess(es)!")
            print(f"=========================================\n")
            return list(guess)

        # Eliminate every candidate inconsistent with the observed feedback
        remaining = [c for c in remaining if score(guess, c) == feedback]
        print(f"  Candidates remaining: {len(remaining)}")

        if not remaining:
            print("  No candidates left - inconsistent state.")
            break

        # Minimax for small sets (exact best pick); greedy first-pick otherwise (fast)
        guess = _minimax_guess(remaining) if len(remaining) <= GREEDY_THRESHOLD else remaining[0]

    print(f"\nFailed to solve within {max_guesses} guesses.")
    print(f"=========================================\n")
    return list(guess)

if __name__ == "__main__":
    code = get_code()
    print(f"Random Code: {code}")
    result = solve_lock(code)
    print(f"Result:       {result}")
    print(f"Correct Code: {code}")
    print(f"Match: {result == code}")
