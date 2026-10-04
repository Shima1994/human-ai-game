"""Counterbalanced assignment: condition x starting role x board order.

16 cells = 2 conditions x 2 starting roles x 4 board orders. The board
orders form a 4x4 balanced Latin square (Williams design): every board
appears once in every round position, and every board directly precedes
every other board exactly once, so position and carry-over effects are
balanced. Each new participant gets the least-filled cell (see
core.db.allocate_assignment), so every block of 16 registrations covers all
16 cells once, and abandoned sessions free their cell for someone else.
"""

# Board numbers refer to core.words.ROUND_BOARDS (1 = B01, ... 4 = B04).
BOARD_ORDERS = (
    (1, 2, 4, 3),
    (2, 3, 1, 4),
    (3, 4, 2, 1),
    (4, 1, 3, 2),
)
CONDITIONS = ("adaptive", "baseline")
STARTING_ROLES = ("ai_clue", "human_clue")

# A session with no logged activity for this long (and not completed) is
# treated as abandoned and stops occupying its cell. Every gameplay action is
# logged and decision timers are at most 120 s, so an active participant is
# never idle this long.
ABANDONED_AFTER_MINUTES = 20


def _cell(index):
    # Ordered so that any partial block is still as balanced as possible:
    # condition alternates every participant, each consecutive pair shares a
    # board order, and the 8 cells of each half cover all 4 board orders with
    # both starting roles equally often.
    pair = index // 2
    return {
        "cell_index": index,
        "condition": CONDITIONS[index % 2],
        "board_order_index": pair % 4,
        "round_board_order": list(BOARD_ORDERS[pair % 4]),
        "starting_role": STARTING_ROLES[(pair + index // 8) % 2],
    }


ASSIGNMENT_CELLS = tuple(_cell(index) for index in range(16))


def board_order_label(round_board_order):
    return "-".join(f"B{number:02d}" for number in round_board_order)
