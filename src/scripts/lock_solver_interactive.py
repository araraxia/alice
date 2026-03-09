from concurrent.futures import ProcessPoolExecutor
from itertools import product
import multiprocessing
import os

MAX_GUESSES = 12
MAX_OPTIONS = 12
CODE_LENGTH = 4
GREEDY_THRESHOLD = 10000 # When to switch from minimax to greedy first-pick for speed


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


def prompt_feedback(guess: tuple, code_len: int) -> tuple[int, int] | None:
    """Ask the user for feedback on the current guess.

    Returns (correct_pos, correct_num), or None if the user requests an undo.
    Type 'u' or 'undo' at the first prompt to undo the last guess.
    """
    print(f"  Enter feedback for guess {list(guess)} (or type 'undo' to go back):")
    while True:
        try:
            raw = (
                input(f"    Correct number, correct position (0-{code_len}): ")
                .strip()
                .lower()
            )
            if raw in ("u", "undo"):
                return None
            correct_pos = int(raw)
            correct_num = int(
                input(f"    Correct number, wrong position   (0-{code_len}): ")
            )
            if (
                0 <= correct_pos <= code_len
                and 0 <= correct_num <= code_len
                and correct_pos + correct_num <= code_len
            ):
                return correct_pos, correct_num
            print(
                "  Invalid values - counts must be non-negative and sum to at most the code length."
            )
        except ValueError:
            print("  Please enter whole numbers only.")


def prompt_settings() -> tuple[int, int, int]:
    """Prompt the user to configure the game. Press Enter to accept each default."""
    print(f"\nGame settings (press Enter to use defaults):")

    def prompt_int(label: str, default: int, min_val: int, max_val: int) -> int:
        while True:
            raw = input(f"  {label} [{default}]: ").strip()
            if raw == "":
                return default
            try:
                value = int(raw)
                if min_val <= value <= max_val:
                    return value
                print(f"  Please enter a number between {min_val} and {max_val}.")
            except ValueError:
                print("  Please enter a whole number.")

    code_len  = prompt_int(f"Code length       (1-10)",  CODE_LENGTH,  1, 10)
    max_opts  = prompt_int(f"Max option value  (2-36)",  MAX_OPTIONS,  2, 36)
    max_guess = prompt_int(f"Maximum guesses   (1-99)",  MAX_GUESSES,  1, 99)
    return code_len, max_opts, max_guess


def solve_lock(
    code_len: int = CODE_LENGTH,
    max_options: int = MAX_OPTIONS,
    max_guesses: int = MAX_GUESSES,
) -> list:
    """
    Interactively solves the lock using constraint elimination + minimax selection.
    After each guess the user provides feedback which is used to discard any
    candidate that could not have produced that same feedback, shrinking the
    search space each round.
    """
    print(f"\n====================================================================")
    print(f"Interactive solver | code length: {code_len}, options: 1-{max_options}")
    print(f"Think of a {code_len}-digit code using numbers 1-{max_options}.")
    print(f"====================================================================")

    all_codes = list(product(range(1, max_options + 1), repeat=code_len))
    remaining = all_codes.copy()

    # history stores (guess, remaining_before_guess) for undo support
    history: list[tuple[tuple, list]] = []

    # Spread first guess (e.g. [1,2,3,4]) probes distinct values, eliminating more candidates
    guess = tuple((i % max_options) + 1 for i in range(code_len))
    attempt = 1

    while attempt <= max_guesses:
        print(f"\nGuess #{attempt}: {list(guess)}")

        feedback = prompt_feedback(guess, code_len)

        if feedback is None:  # undo requested
            if not history:
                print("  Nothing to undo - this is the first guess.")
                continue
            guess, remaining = history.pop()
            attempt -= 1
            print(f"  Undone. Back to guess #{attempt}.")
            continue

        print(f"  Correct position: {feedback[0]}  |  Wrong position: {feedback[1]}")

        if feedback[0] == code_len:
            print(f"\nSolved in {attempt} guess(es)!")
            print(f"=========================================\n")
            return list(guess)

        # Save state before narrowing so it can be restored on undo
        history.append((guess, remaining.copy()))

        # Eliminate every candidate inconsistent with the observed feedback
        remaining = [c for c in remaining if score(guess, c) == feedback]
        print(f"  Candidates remaining: {len(remaining)}")

        if not remaining:
            print("  No candidates left - the feedback entered may contain an error.")
            break

        # Minimax for small sets (exact best pick); greedy first-pick otherwise (fast)
        guess = (
            _minimax_guess(remaining)
            if len(remaining) <= GREEDY_THRESHOLD
            else remaining[0]
        )
        attempt += 1

    print(f"\nFailed to solve within {max_guesses} guesses.")
    print(f"=========================================\n")
    return list(guess)


if __name__ == "__main__":
    # Required for ProcessPoolExecutor in PyInstaller frozen executables on Windows.
    # Prevents spawned worker processes from re-executing solve_lock().
    multiprocessing.freeze_support()
    print("")
    while True:
        code_len, max_opts, max_guess = prompt_settings()
        solve_lock(code_len=code_len, max_options=max_opts, max_guesses=max_guess)
        print('''
                                                                *                         
                                #=%                           #--#                        
                              #--*-#                        #--#--*                       
                            #--=----#                     #---#---=                       
                          #=---:..+#+                   #----#.*:+-#                      
                         #----#.....:#  =########%#*= =*-----.....##                      
                       #-----=.......#=---------------------#......#                      
                      #------#.......*-------------------------#....*                     
                     #-------#......#-----------------------------#.#                     
                   #*--------#--------------------------------------**                    
                ##=*--------------------------------------------------+#                  
             #--#-#----------------*------------------------------------*                 
          #=**#=-#------------------#--------------------------*----------#               
        #*=  #---------------+---*--=.*----------------#-#------=----------#              
      ##    #----------------+---#---#..=----#----------#-*-----+-----------*             
    #*     #-----*---------------==--*...*----#----------+=------#-#-------.+*            
   ##     #:...-------------#----=#---:...*---+=---------#-*-----#=-#----.-..##           
  #*     #-:..--#:.:--::----+----=-----....+---#---------#*#---*-=*-.#-.-.---+-#          
 ++     #------+-..:....:--=--..-#.=---.....---#----..-.-#.*=+-.-+.*:=--------**          
*#      *------*-----------#--:--+.*-=......*-.*#--------=.=#----#.=--+-------#-#         
*      #------+------------#----##:*-#......:--**---*-#-=.:+#-#=*...----------#*#         
#      #------#------------+---#...=##.......--++-#....+.:########-.-*--------###         
*     #----------------------+:...=####+#*=#.#..........#*.=###:..-#=*--------*#*         
*     #------#------------=+-.=##:......:#...............#+..####=..*#---#---# #          
      *------*------------+.*#...=#####*.................#########*..#=---*-#             
      =------=------------*##......#######..............=#######*##..:#---+-#             
#     ------=-------------##...*###########.............:##*####*##..==#-----#            
#     ------#-------------##...#########*##..............###****##*..-..#-----+           
*     =-----#-------------*#...-##*####**##...............=######........#----#           
-#    *-----#-------------+:#...*##*****##.............+............:..:.:+----#          
#=    #-----#-------------==.:....######........................:=:+:+::+:*----*          
 +#   #-----#--------------#....-:::::..........................+:#:+::-:::+----#         
   #   #----#--------------#.::+:=:=:*::.........................#:+:::::..#----#         
     # #----*--------------#::#:::*:+::..........._.,--+*#####.............*----+         
        #------------------*#.-::*:=:.........*%*:`.......................#-----=         
        *----*-------------=-:.........%.:*..............................#------=         
         #---#--*-----------**............%............................-+-------+         
         *---=--=-----------#-*.......+...%..........................+*---------#         
         #----#----------------:......*....*%%%%%%%%%%*-:::%.......#---------:.-#         
*::-##   #----=--+-----------#-=.....::...................#+.::#*+--------..-..=%         
..##     #-----#--=----------=---*#-.%...............#%#=-*#=-----=-----.------##         
.*       *------+-=---------..#-#-#**%...............:##**------=-#-----------#-#         
*        =..-.--=-.+---.-.:-..-**#*##................-****##------#----------*#*          
        #---#:---+-------------#**#*#................%*****##=-+-#+---------* *#          
        #---+-----*-------------#**#................=#***#*#==+*=-*--------#  #           
        -----------*------------+*-..........:=#%#******#**#===#--#------=*  #            
*      #------#-----=-------------........-*##==###****#***#====#+-----=#                 
''')
        input("Press Enter to play again. Ctrl+C to exit.")
