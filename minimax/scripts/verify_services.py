"""Clean-environment service acceptance, without spending model tokens."""
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sdd.core import ROOT, Database, PowerContext, context, documents, write_json

task = json.loads((ROOT / 'task.json').read_text(encoding='utf-8'))
task['id'] += '-service-' + os.urandom(6).hex()
db = Database()
db.import_all(documents())
pc = PowerContext(task['id'])
initial = context(db, pc, task)
assert not initial['previous_progress'].get('content'), 'Expected empty initial task state'
marker = 'service-check-' + os.urandom(6).hex()
state = {'completed': ['imported sources', marker], 'todo': ['review current tests'],
         'validation': {'status': 'service verification only'}}
pc.save(state)
script = ('import json; from sdd.core import *; '
          't=json.loads((ROOT/"task.json").read_text()); '
          't["id"]=' + repr(task['id']) + '; '
          'print(json.dumps(context(Database(),PowerContext(t["id"]),t)))')
child = subprocess.run([sys.executable, '-B', '-c', script], cwd=ROOT,
                       capture_output=True, text=True, check=True)
resumed = json.loads(child.stdout)
assert marker in resumed['previous_progress'].get('content', '')
assert resumed['next_action'].startswith('Review saved')
subprocess.run([sys.executable, '-m', 'sdd', 'refresh-check', '--output',
                str(ROOT / 'runtime/service-refresh.json')], cwd=ROOT, check=True)
write_json(ROOT / 'runtime/service-replay.json', {'passed': True, 'before': initial, 'after': resumed})
print('Real database import/query, empty-state save, new-process recall, state use and spec refresh passed.')
