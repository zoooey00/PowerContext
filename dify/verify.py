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
    req = Request('http://127.0.0.1:8099' + path, json.dumps(body, ensure_ascii=False).encode(),
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
    env['POWERCONTEXT_URL'] = 'http://127.0.0.1:8000'
    env['POWERCONTEXT_SERVER_HTTP_PORT'] = '8000'
    env['POWERCONTEXT_SERVER_MCP_ENABLED'] = 'false'
    records = {'tested_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
               'scope': 'real PowerContext HTTP + gateway; deterministic test replies; no Dify or LLM execution',
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
                wait('http://127.0.0.1:8000/health/live', p)
                return p
            pc = start_pc()
            shop = subprocess.Popen([sys.executable, str(ROOT / 'server.py')], env=env, stdout=logs, stderr=logs)
            processes.append(shop)
            wait('http://127.0.0.1:8099/health', shop)
            def prepare(action, item, user='judge-a', player='月亮来客'):
                payload = {'user': user, 'player': player, 'action': action, 'item': item, 'request_id': uuid.uuid4().hex}
                r = post('/prepare', payload, token)
                records['steps'].append({'prepare_input': payload, 'prepare_result': {k:v for k,v in r.items() if k != 'ticket'}})
                return r
            def save(prepared, reply):
                r = post('/commit', {'ticket': prepared['ticket'], 'reply': reply}, token)
                records['steps'].append({'test_reply': reply, 'commit_result': r})
                return r
            a = prepare('prank', '会打嗝的月亮')
            assert a['before']['turn'] == 0 and a['memory_count'] == 0
            first = save(a, '测试台词：阿扣被会打嗝的月亮喷了一脸星星。')
            assert first['state']['suspicion'] == 2 and first['state']['price'] == 7
            duplicate = save(a, '重复台词不应覆盖')
            assert duplicate['duplicate'] and duplicate['reply'] == first['reply']
            # Restart the actual PowerContext process: persistence cannot come from gateway RAM.
            pc.terminate()
            pc.wait(timeout=20)
            pc = start_pc()
            b = prepare('trade', '一双失眠的拖鞋')
            assert '会打嗝的月亮' in b['memories'] and b['before']['price'] == 7
            assert b['memory_ref']
            other = prepare('look', '看看柜台', user='judge-b')
            assert other['memory_count'] == 0 and other['before']['price'] == 3
            fork = prepare('look', '另一张同时打开的标签页')
            save(b, '测试台词：月亮来客，又是你！拖鞋需要七枚纽扣。')
            try:
                save(fork, '过期回合')
                raise AssertionError('应拒绝冲突回合')
            except HTTPError as error:
                assert error.code == 400
                records['steps'].append({'stale_turn_rejected': error.code})
            c = prepare('apologize', '带一颗薄荷糖来赔礼')
            final = save(c, '测试台词：看在薄荷糖的份上，下回少收两枚纽扣。')
            assert final['state']['suspicion'] == 1 and final['state']['price'] == 5
            try:
                post('/prepare', {'action': 'look'}, 'incorrect')
                raise AssertionError('未鉴权请求应拒绝')
            except HTTPError as error:
                assert error.code == 401
            records['checks'] = ['empty archive', 'real memory write/readback', 'duplicate commit',
                'PowerContext process restart persistence', 'recall changes price', 'player isolation',
                'stale turn rejected', 'apology lowers price', 'unauthorized request rejected']
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
