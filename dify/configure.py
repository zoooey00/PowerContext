"""生成本机密钥与已绑定的私有导入 DSL；不把凭据提交仓库。"""
import argparse
import json
from pathlib import Path
import secrets
from urllib.parse import urlparse
from build_dsl import build

root = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--url', default='http://host.docker.internal:8099')
args = parser.parse_args()
if urlparse(args.url).scheme not in ('http', 'https'):
    raise SystemExit('需要 HTTP/HTTPS 网关地址')
env = root / '.env'
values = {}
if env.exists():
    for line in env.read_text(encoding='utf-8').splitlines():
        if '=' in line:
            k, v = line.split('=', 1)
            values[k] = v
if len(values.get('SHOP_TOKEN', '')) < 24 or values.get('SHOP_TOKEN', '').startswith('replace-'):
    values['SHOP_TOKEN'] = secrets.token_hex(24)
values.setdefault('SHOP_HOST', '127.0.0.1')
values['SHOP_PUBLIC_URL'] = args.url.rstrip('/')
env.write_text('\n'.join(k+'='+v for k, v in values.items())+'\n', encoding='utf-8')
app = build()
for variable in app['workflow']['environment_variables']:
    variable['value'] = args.url.rstrip('/') if variable['name'] == 'SHOP_URL' else values['SHOP_TOKEN']
local = root / '.local'
local.mkdir(exist_ok=True)
(local / 'grudge-shop.yml').write_text(json.dumps(app, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print('已生成 .local/grudge-shop.yml，可直接导入；含本机凭据，请勿公开或提交。')
