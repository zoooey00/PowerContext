"""Resumable range download helper for slow connections; validates all byte counts."""
import concurrent.futures
import pathlib
import subprocess
import sys

url, target, total = sys.argv[1], pathlib.Path(sys.argv[2]), int(sys.argv[3])
target.parent.mkdir(parents=True, exist_ok=True)
parts = target.parent / (target.name + '.parts')
parts.mkdir(exist_ok=True)
size = 1024 * 1024

def download(index):
    start = index * size
    end = min(total, start + size) - 1
    part = parts / str(index)
    for attempt in range(4):
        received = part.stat().st_size if part.exists() else 0
        if received == end - start + 1:
            break
        if received > end - start + 1:
            raise RuntimeError('Server ignored range request')
        tail = parts / f'{index}.tail'
        subprocess.run(['curl.exe', '-f', '-sS', '-L', '--max-time', '180', '-r', f'{start+received}-{end}', '-o', str(tail), url], check=False)
        if tail.exists():
            data = tail.read_bytes()
            if len(data) > end - start + 1 - received:
                raise RuntimeError('Server ignored range request')
            with part.open('ab') as output:
                output.write(data)
            tail.unlink()
    if part.stat().st_size != end - start + 1:
        raise RuntimeError(f'Invalid range response: {index}')
    print(f'{target.name}: {index + 1}/{(total + size - 1)//size}', flush=True)

with concurrent.futures.ThreadPoolExecutor(max_workers=24) as pool:
    list(pool.map(download, range((total + size - 1)//size)))
with target.open('wb') as output:
    for i in range((total + size - 1)//size):
        output.write((parts / str(i)).read_bytes())
assert target.stat().st_size == total
