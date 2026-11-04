import unittest
from business.tickets import list_tickets
from tests.data import ROWS


class TargetTests(unittest.TestCase):
    def test_open(self):
        self.assertEqual([r['id'] for r in list_tickets(ROWS, status='open')], [1, 3])

    def test_closed(self):
        self.assertEqual([r['id'] for r in list_tickets(ROWS, status='closed')], [2])

    def test_normalization(self):
        self.assertEqual([r['id'] for r in list_tickets(ROWS, status=' OPEN ')], [1, 3])

    def test_combined(self):
        self.assertEqual([r['id'] for r in list_tickets(ROWS, owner='alice', status='open')], [3])

    def test_invalid(self):
        for status in ['', 'pending', 0, False, [], {}]:
            with self.subTest(status=status), self.assertRaises(ValueError):
                list_tickets(ROWS, status=status)

    def test_empty_invalid(self):
        with self.assertRaises(ValueError):
            list_tickets([], status='pending')
