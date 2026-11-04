"""Optional official 7-day seekdb sandbox. Secrets are written locally, never printed."""
import json
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parents[1]
request = urllib.request.Request('https://d0.seekdb.ai/api/v1/instances', data=b'', method='POST')
with urllib.request.urlopen(request, timeout=60) as response:
    result = json.load(response)
path = root / 'runtime/seekdb-instance.json'
path.parent.mkdir(exist_ok=True)
path.write_text(json.dumps(result), encoding='utf-8')
print('Official seekdb response saved locally (excluded from Git); top-level fields:', list(result))
