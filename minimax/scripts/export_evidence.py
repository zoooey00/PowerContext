"""Export only known review artifacts, excluding credentials and private model reasoning."""
import json
import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[1]
runtime = root / 'runtime'
target = root / 'evidence/live'
target.mkdir(parents=True, exist_ok=True)
required = ['minimax-generation.json', 'generated-tests.json', 'context-before.json',
            'context-resumed.json', 'spec-refresh.json', 'acceptance.json', 'change.patch', 'events.jsonl']
missing = [name for name in required if not (runtime / name).exists()]
if missing:
    raise SystemExit('Cannot export incomplete proof: ' + ', '.join(missing))
accepted = json.loads((runtime / 'acceptance.json').read_text(encoding='utf-8'))
if not accepted.get('passed'):
    raise SystemExit('Acceptance run did not pass')
for name in required:
    if name != 'events.jsonl':
        shutil.copyfile(runtime / name, target / name)
events = [json.loads(line) for line in (runtime / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
start = next(i for i, event in enumerate(events) if event.get('path') == '/v1/scopes'
             and event.get('request', {}).get('idempotency_key') == 'minimax-sdd-' + accepted['task_id'])
end = max(i for i, event in enumerate(events) if event['event'] == 'database_import')
# Export this successful demo only, excluding earlier diagnostics and later unit-test events.
(target / 'events.jsonl').write_text('\n'.join(json.dumps(e, ensure_ascii=False)
                                             for e in events[start:end + 1]) + '\n', encoding='utf-8')
shutil.copyfile(root / 'business/tickets.py', root / 'fixtures/after/tickets.py')
print('Exported real execution evidence; no instance credentials or .env were copied.')
