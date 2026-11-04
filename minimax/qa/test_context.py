"""Unit checks for source selection contracts; these do not prove external service use."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from sdd.core import ROOT, context, documents


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.rows = documents()
        self.task = json.loads((ROOT / 'task.json').read_text(encoding='utf-8'))

    def build(self, rows):
        class DB:
            def search(self, terms):
                return rows
        class PC:
            def read(self):
                return {'status': 'ready', 'content': 'previous test evidence'}
        return context(DB(), PC(), self.task)

    def test_source_ids_exist(self):
        self.assertTrue(set(self.task['required']) <= {r['id'] for r in self.rows})

    def test_missing_spec_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'Missing required sources'):
            self.build([r for r in self.rows if r['id'] != 'TICKET-002'])

    def test_stale_content_rejected(self):
        rows = copy.deepcopy(self.rows)
        rows[0]['sha256'] = 'stale'
        with self.assertRaisesRegex(RuntimeError, 'Stale index'):
            self.build(rows)

    def test_history_used(self):
        self.assertIn('Review saved', self.build(self.rows)['next_action'])

    def test_revision_import_reads_disk(self):
        scratch = ROOT / 'runtime'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as folder:
            root = Path(folder)
            (root / 'specs').mkdir()
            path = root / 'specs/change.json'
            path.write_text(json.dumps({'revision': 1, 'entries': [
                {'id': 'S1', 'tags': ['tickets'], 'text': 'initial'}]}))
            first = documents(root)[0]
            path.write_text(json.dumps({'revision': 2, 'entries': [
                {'id': 'S1', 'tags': ['tickets'], 'text': 'updated'}]}))
            second = documents(root)[0]
            self.assertEqual(second['content'], 'updated')
            self.assertNotEqual(first['sha256'], second['sha256'])
