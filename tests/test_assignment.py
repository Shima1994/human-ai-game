import itertools
import unittest
from collections import Counter

from core.assignment import (
    ASSIGNMENT_CELLS,
    BOARD_ORDERS,
    CONDITIONS,
    STARTING_ROLES,
    board_order_label,
)


def _least_filled(occupancy):
    """Mirror of core.db.allocate_assignment's choice rule."""
    cell = min(ASSIGNMENT_CELLS, key=lambda c: (occupancy[c["cell_index"]], c["cell_index"]))
    return cell


def _role_for_round(starting_role, round_number):
    if round_number % 2 == 1:
        return starting_role
    return "ai_clue" if starting_role == "human_clue" else "human_clue"


class LatinSquareTests(unittest.TestCase):
    def test_every_board_appears_once_in_every_position(self):
        for position in range(4):
            self.assertEqual(sorted(order[position] for order in BOARD_ORDERS), [1, 2, 3, 4])

    def test_every_board_precedes_every_other_board_exactly_once(self):
        pairs = Counter(
            (order[i], order[i + 1]) for order in BOARD_ORDERS for i in range(3)
        )
        expected = {(a, b) for a, b in itertools.permutations([1, 2, 3, 4], 2)}
        self.assertEqual(set(pairs), expected)
        self.assertTrue(all(count == 1 for count in pairs.values()))


class CellTests(unittest.TestCase):
    def test_sixteen_unique_cells_cover_the_full_design(self):
        combos = {
            (c["condition"], c["starting_role"], tuple(c["round_board_order"]))
            for c in ASSIGNMENT_CELLS
        }
        self.assertEqual(len(ASSIGNMENT_CELLS), 16)
        self.assertEqual(
            combos,
            set(itertools.product(CONDITIONS, STARTING_ROLES, BOARD_ORDERS)),
        )

    def test_first_eight_cells_are_already_balanced(self):
        first_half = ASSIGNMENT_CELLS[:8]
        self.assertEqual(Counter(c["condition"] for c in first_half), {"adaptive": 4, "baseline": 4})
        self.assertEqual(Counter(c["starting_role"] for c in first_half), {"ai_clue": 4, "human_clue": 4})
        self.assertEqual(Counter(c["board_order_index"] for c in first_half), {0: 2, 1: 2, 2: 2, 3: 2})

    def test_label(self):
        self.assertEqual(board_order_label([1, 2, 4, 3]), "B01-B02-B04-B03")


class AllocationSimulationTests(unittest.TestCase):
    def test_every_block_of_sixteen_covers_all_cells(self):
        occupancy = Counter({c["cell_index"]: 0 for c in ASSIGNMENT_CELLS})
        assigned = []
        for _ in range(16 * 12):
            cell = _least_filled(occupancy)
            occupancy[cell["cell_index"]] += 1
            assigned.append(cell["cell_index"])
        for block_start in range(0, len(assigned), 16):
            self.assertEqual(sorted(assigned[block_start:block_start + 16]), list(range(16)))

    def test_board_by_position_by_starting_role_is_balanced_for_each_condition(self):
        """48 completers (3 full cycles): within each condition, each board is
        the round-k board exactly 3 times when the AI starts and 3 times when
        the human starts -- and is played in each role equally often."""
        occupancy = Counter({c["cell_index"]: 0 for c in ASSIGNMENT_CELLS})
        cells = []
        for _ in range(48):
            cell = _least_filled(occupancy)
            occupancy[cell["cell_index"]] += 1
            cells.append(cell)
        for condition in CONDITIONS:
            mine = [c for c in cells if c["condition"] == condition]
            by_position = Counter(
                (c["starting_role"], position, c["round_board_order"][position])
                for c in mine
                for position in range(4)
            )
            self.assertEqual(len(by_position), 2 * 4 * 4)
            self.assertTrue(all(count == 3 for count in by_position.values()))
            by_role = Counter(
                (board, _role_for_round(c["starting_role"], position + 1))
                for c in mine
                for position, board in enumerate(c["round_board_order"])
            )
            self.assertTrue(all(count == 12 for count in by_role.values()))

    def test_abandoned_cell_is_refilled_by_the_next_participant(self):
        occupancy = Counter({c["cell_index"]: 0 for c in ASSIGNMENT_CELLS})
        for _ in range(5):
            occupancy[_least_filled(occupancy)["cell_index"]] += 1
        # The participant in cell 2 abandons and stops counting as occupied.
        occupancy[2] -= 1
        self.assertEqual(_least_filled(occupancy)["cell_index"], 2)


if __name__ == "__main__":
    unittest.main()
