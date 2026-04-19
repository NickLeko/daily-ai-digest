import unittest

import formatter
import operator_brief
import scoring
from selection_policy import (
    DAILY_STORY_LIMIT,
    ITEM_OBJECTIVE_MIN_SCORES,
    STORY_OBJECTIVE_MIN_SCORES,
    threshold_keys_are_aligned,
)


class SelectionPolicyTests(unittest.TestCase):
    def test_thresholds_are_sourced_from_selection_policy(self) -> None:
        self.assertTrue(threshold_keys_are_aligned())
        self.assertIs(scoring.OBJECTIVE_MIN_SCORE, ITEM_OBJECTIVE_MIN_SCORES)
        self.assertIs(operator_brief.OBJECTIVE_MIN_SCORES, STORY_OBJECTIVE_MIN_SCORES)
        self.assertEqual(formatter.DAILY_STORY_LIMIT, DAILY_STORY_LIMIT)


if __name__ == "__main__":
    unittest.main()
