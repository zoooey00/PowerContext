import copy
import unittest
from business.tickets import list_tickets
from tests.data import ROWS


class RegressionTests(unittest.TestCase):
    def test_default_and_order(self):
        self.assertEqual([r['id'] for r in list_tickets(ROWS)], [1, 2, 3])

    def test_owner(self):
        self.assertEqual([r['id'] for r in list_tickets(ROWS, owner='alice')], [2, 3])

    def test_unknown_owner(self):
        self.assertEqual(list_tickets(ROWS, owner='nobody'), [])

    def test_exact_owner(self):
        self.assertEqual(list_tickets(ROWS, owner='ALICE'), [])

    def test_empty(self):
        self.assertEqual(list_tickets([]), [])

    def test_independent_rows(self):
        original = copy.deepcopy(ROWS)
        result = list_tickets(ROWS)
        result[0]['title'] = 'changed'
        self.assertEqual(ROWS, original)
