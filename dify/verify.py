"""真实 PowerContext HTTP 验证；不会把规则台词冒充模型输出或 Dify 运行。"""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import uuid

ROOT = Path(__file__).parent


def post(path, body, token):
    req = Request('http://127.0.0.1:8101' + path, json.dumps(body, ensure_ascii=False).encode(),
                  {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token})
    with urlopen(req, timeout=60) as r:
        return json.load(r)


def wait(url, process):
    for _ in range(120):
        if process.poll() is not None:
            raise RuntimeError('服务退出，请检查日志')
        try:
            with urlopen(url, timeout=1) as r:
                if r.status == 200:
                    return
        except (URLError, OSError):
            time.sleep(0.5)
    raise RuntimeError('服务启动超时')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default=str(ROOT / 'evidence' / 'backend-run.json'))
    args = parser.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    token = uuid.uuid4().hex
    env['SHOP_TOKEN'] = token
    env['SHOP_PORT'] = '8101'
    env['POWERCONTEXT_URL'] = 'http://127.0.0.1:8011'
    env['POWERCONTEXT_SERVER_HTTP_PORT'] = '8011'
    env['POWERCONTEXT_SERVER_MCP_ENABLED'] = 'false'
    records = {'tested_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
               'scope': 'real PowerContext HTTP + generic adapter; exact Dify code functions executed locally; no hosted Dify or LLM execution',
               'environment': {'python': platform.python_version(), 'os': platform.platform(),
                               'powercontext_distribution': importlib.metadata.version('powercontext'),
                               'powercontext_source': json.loads(importlib.metadata.distribution('powercontext').read_text('direct_url.json'))}, 'steps': []}
    processes = []
    with tempfile.TemporaryDirectory(prefix='grudge-shop-') as folder:
        env['POWERCONTEXT_SERVER_DATABASE'] = json.dumps({'kind': 'sqlite', 'url': 'sqlite+aiosqlite:///' + (Path(folder) / 'pc.db').as_posix()})
        env['POWERCONTEXT_SERVER_WORKSPACE'] = folder
        logs = open(out.parent / 'services.log', 'w', encoding='utf-8')
        try:
            def start_pc():
                cli = str(Path(sys.executable).parent / ('powercontext.exe' if os.name == 'nt' else 'powercontext'))
                p = subprocess.Popen([cli, 'server', 'run'], env=env, cwd=folder, stdout=logs, stderr=logs)
                processes.append(p)
                wait('http://127.0.0.1:8011/health/live', p)
                return p
            pc = start_pc()
            shop = subprocess.Popen([sys.executable, str(ROOT / 'server.py')], env=env, stdout=logs, stderr=logs)
            processes.append(shop)
            wait('http://127.0.0.1:8101/health', shop)
            from game_nodes import input_node, settle_node, render_node, receipt_node
            code = uuid.uuid4().hex
            def turn(query, secret=code):
                cmd = input_node('验收存档', secret, query, uuid.uuid4().hex)
                read = post('/memory/read', json.loads(cmd['body']), token)
                result = settle_node(json.dumps(read), 200, cmd['command'])
                return read, result
            read, result = turn('恶作剧：会打嗝的月亮')
            assert result['allowed'] == 'yes'
            rendered = render_node(result['ticket'], result['event'], result['history'], '{"tone":"astonished"}')
            first = post('/memory/append', json.loads(rendered['body']), token)
            assert first['saved']
            assert post('/memory/append', json.loads(rendered['body']), token)['duplicate']
            pc.terminate(); pc.wait(timeout=20); pc = start_pc()
            read, result = turn('交换：一双失眠的拖鞋')
            assert '会打嗝的月亮' in result['history']
            assert json.loads(result['event'])['after']['price'] == 7
            r = render_node(result['ticket'], result['event'], result['history'], '拿拖鞋换走月亮')
            assert r['model_guard'] == 'fallback' and '拿拖鞋换走月亮' not in r['answer']
            post('/memory/append', json.loads(r['body']), token)
            _, other = turn('看看：柜台', uuid.uuid4().hex)
            assert json.loads(other['before'])['turn'] == 0
            _, result = turn('道歉：薄荷糖')
            r = render_node(result['ticket'], result['event'], result['history'], '{"tone":"soft"}')
            assert '实际换得：失眠计数器' in r['answer']
            saved = post('/memory/append', json.loads(r['body']), token)
            receipt = receipt_node(json.dumps(saved), 200, r['answer'])
            assert '交换价 5 枚纽扣' in receipt['answer']
            records['steps'] = [{'recall_records': read['records'], 'rendered_result': r['answer'], 'readback_refs': saved['references']}]
            # 使用 Dify 节点本身的函数源码测试上限和双向钳位，网关不参与结算。
            history = [{'turn':i+1,'action':'prank','item':'道具','exchange':None} for i in range(20)]
            limited = settle_node(json.dumps({'records':history,'ticket':'test'}),200,'{"action":"look","item":"柜台"}')
            assert limited['allowed'] == 'no' and json.loads(limited['before'])['suspicion'] == 5
            for row in history: row['action'] = 'apologize'
            limited = settle_node(json.dumps({'records':history,'ticket':'test'}),200,'{"action":"look","item":"柜台"}')
            assert json.loads(limited['before'])['suspicion'] == 0
            try:
                post('/memory/read', {}, 'wrong')
                raise AssertionError('鉴权失效')
            except HTTPError as error: assert error.code == 401
            records['checks'] = ['actual PowerContext write/readback', 'restart persistence', 'duplicate idempotency', 'secret archive isolation', 'Dify code state replay', 'Dify code 20-turn gate', 'Dify code clamps', 'untrusted model output fallback', 'exact exchange ledger', 'gateway authentication']
            records['passed'] = True
            out.write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            print(json.dumps({'passed': True, 'checks': records['checks'], 'evidence': str(out)}, ensure_ascii=False))
        finally:
            for p in reversed(processes):
                if p.poll() is None:
                    p.terminate()
                    p.wait(timeout=20)
            logs.close()


if __name__ == '__main__':
    main()
