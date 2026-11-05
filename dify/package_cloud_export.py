"""校验并脱敏 Dify Cloud 的官方 .dify 导出，保留可导入包和内嵌 DSL。"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
import yaml
from dotenv import dotenv_values

root = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('export', help='从 Dify 导出的 .dify 文件路径')
args = parser.parse_args()
with zipfile.ZipFile(args.export) as archive:
    original = archive.read('app.yaml')
    manifest = yaml.safe_load(archive.read('manifest.yaml'))
    expected = next(x for x in manifest['apps'] if x['path'] == 'app.yaml')
    assert expected['size'] == len(original)
    assert expected['sha256'] == hashlib.sha256(original).hexdigest()
    app = yaml.safe_load(original)
    for variable in app['workflow']['environment_variables']:
        if variable['name'] == 'SHOP_URL':
            variable['value'] = 'https://your-game-gateway.example'
        if variable['value_type'] == 'secret':
            variable['value'] = ''
    content = yaml.safe_dump(app, allow_unicode=True, sort_keys=False).encode('utf-8')
    for key, secret in dotenv_values(root / '.env').items():
        if secret and ('TOKEN' in key or 'KEY' in key):
            assert secret.encode() not in content, '拒绝交付包含真实凭据的导出'
    (root / 'grudge-shop-cloud.yml').write_bytes(content)
    final_manifest = {'format': 'dify.app', 'format_version': 1, 'apps': [
        {'path': 'app.yaml', 'size': len(content), 'sha256': hashlib.sha256(content).hexdigest()}]}
    with zipfile.ZipFile(root / 'grudge-shop.dify', 'w', zipfile.ZIP_DEFLATED) as output:
        output.writestr('manifest.yaml', yaml.safe_dump(final_manifest, sort_keys=False))
        output.writestr('app.yaml', content)
    print(json.dumps({'packaged': True, 'dsl_version': app['version'], 'secrets_removed': True}))
