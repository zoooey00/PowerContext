"""记仇杂货铺：仅做 PowerContext 记录读写的适配器。Python 3.12。"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

PC_URL = os.environ.get('POWERCONTEXT_URL', 'http://127.0.0.1:8000').rstrip('/')
PC_TOKEN = os.environ.get('POWERCONTEXT_TOKEN', '')
SHOP_TOKEN = os.environ.get('SHOP_TOKEN', '')
SIGN_KEY = secrets.token_bytes(32)
LOCK = threading.Lock()



def pc(path, data):
    headers = {'Content-Type': 'application/json'}
    if PC_TOKEN:
        headers['Authorization'] = 'Bearer ' + PC_TOKEN
    req = Request(PC_URL + path, json.dumps(data, ensure_ascii=False).encode(), headers)
    with urlopen(req, timeout=30) as response:
        return json.load(response)


def scope(namespace):
    return pc('/v1/scopes', {'title': 'Dify memory ' + namespace[:12],
        'summary': 'Dify application-owned structured records',
        'idempotency_key': 'dify-records-v2-' + namespace})['scope_id']


def history(sid):
    result = pc('/v1/memory/entries/list', {'scope_id': sid, 'limit': 100})
    if result.get('next_cursor'):
        raise ValueError('记录分页超出此演示适配器上限')
    rows = []
    for entry in result['entries']:
        row = json.loads(entry['text'])
        if row.get('schema') == 'dify-record-v2':
            rows.append(row)
    rows.sort(key=lambda r: r['sequence'])
    refs = sorted([e['artifact'] for e in result['entries']], key=lambda r: r['artifact_id'])
    return rows, refs


def signed(payload):
    raw = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode()
    data = base64.urlsafe_b64encode(raw).decode()
    return data + '.' + hmac.new(SIGN_KEY, data.encode(), hashlib.sha256).hexdigest()


def unpack(ticket):
    data, signature = ticket.rsplit('.', 1)
    if not hmac.compare_digest(signature, hmac.new(SIGN_KEY, data.encode(), hashlib.sha256).hexdigest()):
        raise ValueError('无效回合凭据')
    payload = json.loads(base64.urlsafe_b64decode(data))
    if time.time() - payload['issued'] > 600:
        raise ValueError('回合已过期，请重新运行')
    return payload


def text(data, key, limit):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f'{key} 必须是 1–{limit} 字符的文本')
    return value.strip()


def read_memory(data):
    namespace = text(data, 'namespace', 64)
    if len(namespace) != 64 or any(c not in '0123456789abcdef' for c in namespace):
        raise ValueError('无效的存档能力标识')
    sid = scope(namespace)
    rows, refs = history(sid)
    payload = {'scope_id': sid, 'request_id': text(data, 'request_id', 100),
               'fingerprint': hashlib.sha256(json.dumps(refs, sort_keys=True).encode()).hexdigest(),
               'issued': time.time()}
    return {'ticket': signed(payload), 'records': [r['data'] for r in rows], 'references': refs}


def append_memory(data):
    payload = unpack(text(data, 'ticket', 6000))
    record = data['record']
    if not isinstance(record, dict) or len(json.dumps(record, ensure_ascii=False).encode()) > 7000:
        raise ValueError('记录格式或大小无效')
    sid = payload['scope_id']
    rows, refs = history(sid)
    for row in rows:
        if row['request_id'] == payload['request_id']:
            if row['data'] != record:
                raise ValueError('同一请求不能写入不同记录')
            return {'saved': True, 'duplicate': True, 'references': refs}
    fingerprint = hashlib.sha256(json.dumps(refs, sort_keys=True).encode()).hexdigest()
    if fingerprint != payload['fingerprint']:
        raise ValueError('并发写入冲突，请重新读取')
    envelope = {'schema': 'dify-record-v2', 'sequence': len(rows) + 1,
                'request_id': payload['request_id'], 'data': record}
    saved = pc('/v1/memory/remember', {'scope_id': sid, 'kind': 'fact',
        'text': json.dumps(envelope, ensure_ascii=False), 'reason': 'Dify 应用显式保存结构化记录'})
    readback, refs = history(sid)
    if not any(r['request_id'] == payload['request_id'] and r['data'] == record for r in readback):
        raise RuntimeError('记录读回不一致')
    return {'saved': True, 'duplicate': False, 'references': refs, 'write_result': saved}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # 不记录请求正文或 token。

    def respond(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.respond(200 if self.path == '/health' else 404, {'service': 'grudge-shop', 'version': '2.0.0'})

    def do_POST(self):
        if not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + SHOP_TOKEN):
            return self.respond(401, {'error': '需要正确的 SHOP_TOKEN'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if size < 1 or size > 20000:
                raise ValueError('请求大小无效')
            data = json.loads(self.rfile.read(size))
            with LOCK:
                if self.path == '/memory/read':
                    result = read_memory(data)
                elif self.path == '/memory/append':
                    result = append_memory(data)
                else:
                    return self.respond(404, {'error': '未知路径'})
            self.respond(200, result)
        except (ValueError, KeyError, TypeError):
            self.respond(400, {'error': '输入、回合凭据或存档状态无效；请检查输入并重新运行。'})
        except HTTPError as error:
            self.respond(502, {'error': 'PowerContext 操作失败', 'upstream_status': error.code})
        except Exception:
            self.respond(503, {'error': '记忆服务暂不可用；本轮未确认保存，请恢复服务后重试。'})


if __name__ == '__main__':
    if len(SHOP_TOKEN) < 24:
        raise SystemExit('请设置至少 24 字符的 SHOP_TOKEN')
    ThreadingHTTPServer((os.environ.get('SHOP_HOST', '127.0.0.1'), int(os.environ.get('SHOP_PORT', '8099'))), Handler).serve_forever()
