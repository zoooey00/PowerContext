"""Replay delivered tests and check evidence consistency without calling a model."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
live = root / 'evidence/live'
sha = lambda s: hashlib.sha256(s.encode('utf-8')).hexdigest()
generation = json.loads((live / 'minimax-generation.json').read_text(encoding='utf-8'))
report = json.loads((live / 'generated-tests.json').read_text(encoding='utf-8'))
code = (root / 'business/tickets.py').read_text(encoding='utf-8')
assert sha(code) == generation['answer_sha256'] == sha(generation['answer'])
assert sha(code) == report['runs']['after_target']['code_sha256']
test_hashes = {p.name: sha(p.read_text(encoding='utf-8')) for p in (root / 'tests').glob('*.py')}
assert all(run['tests_sha256'] == test_hashes for run in report['runs'].values())
assert report['runs']['before_target']['exit_code'] == 1
assert all(report['runs'][key]['exit_code'] == 0 for key in ['before_regression', 'after_target', 'after_regression'])
ctx = json.loads((live / 'context-before.json').read_text(encoding='utf-8'))
assert set(ctx['task']['required']) <= {row['id'] for row in ctx['sources']}
assert 'BILLING-001' not in {row['id'] for row in ctx['sources']}
assert generation['request']['messages'][1]['content'] == json.dumps(ctx, ensure_ascii=False)
resumed = json.loads((live / 'context-resumed.json').read_text(encoding='utf-8'))
assert 'validated-' in resumed['previous_progress']['content']
assert resumed['next_action'].startswith('Review saved')
assert json.loads((live / 'spec-refresh.json').read_text(encoding='utf-8'))['passed']
for command in [[sys.executable, '-B', '-m', 'unittest', '-v', 'tests.test_target', 'tests.test_regression'],
                [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'qa', '-v']]:
    subprocess.run(command, cwd=root, check=True)
print('Submitted evidence matches code, unchanged tests, model context and restart state; replay passed.')
