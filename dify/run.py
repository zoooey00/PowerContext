"""启动本机 PowerContext 与网关；Ctrl+C 关闭；数据库存放在 dify/.powercontext。"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen
from dotenv import load_dotenv

root = Path(__file__).resolve().parent
load_dotenv(root / '.env')
if len(os.environ.get('SHOP_TOKEN', '')) < 24 or os.environ.get('SHOP_TOKEN', '').startswith('replace-'):
    raise SystemExit('先在 .env 设置一个随机 SHOP_TOKEN，至少 24 字符')
data = root / '.powercontext'
data.mkdir(exist_ok=True)
env = os.environ.copy()
env['POWERCONTEXT_SERVER_DATABASE'] = json.dumps({'kind': 'sqlite', 'url': 'sqlite+aiosqlite:///' + (data / 'pc.db').as_posix()})
env['POWERCONTEXT_SERVER_WORKSPACE'] = str(data)
env['POWERCONTEXT_SERVER_HTTP_HOST'] = '127.0.0.1'
env['POWERCONTEXT_SERVER_HTTP_PORT'] = '8000'
env['POWERCONTEXT_SERVER_MCP_ENABLED'] = 'false'
env['POWERCONTEXT_URL'] = 'http://127.0.0.1:8000'
cli = Path(sys.executable).parent / ('powercontext.exe' if os.name == 'nt' else 'powercontext')
processes = []
try:
    pc = subprocess.Popen([str(cli), 'server', 'run'], env=env, cwd=data)
    processes.append(pc)
    for _ in range(180):
        if pc.poll() is not None:
            raise RuntimeError('PowerContext 启动失败')
        try:
            with urlopen('http://127.0.0.1:8000/health/live', timeout=1) as response:
                if response.status == 200:
                    break
        except (URLError, OSError):
            time.sleep(1)
    else:
        raise RuntimeError('PowerContext 启动超时')
    shop = subprocess.Popen([sys.executable, str(root / 'server.py')], env=env, cwd=root)
    processes.append(shop)
    print('记仇杂货铺网关端口 8099；请在 Dify 配置 SHOP_URL 与相同的 SHOP_TOKEN。', flush=True)
    while all(p.poll() is None for p in processes):
        time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    for p in reversed(processes):
        if p.poll() is None:
            p.terminate()
            p.wait(timeout=30)
