import urllib.request
from pathlib import Path

ref = '2853ed98a6ab767f6bbfe35098024d5f9cec9a2b'
target = Path(__file__).resolve().parents[1] / 'runtime/powercontext.zip'
target.parent.mkdir(exist_ok=True)
urllib.request.urlretrieve('https://codeload.github.com/oceanbase/powercontext/zip/' + ref, target)
print('Downloaded pinned PowerContext source:', target)
