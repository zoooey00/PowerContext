"""记仇杂货铺：Dify 的规则与 PowerContext 记忆网关。Python 3.12。"""
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
LABELS = {'trade': '交换', 'prank': '恶作剧', 'apologize': '道歉', 'look': '看看'}


def pc(path, data):
    headers = {'Content-Type': 'application/json'}
    if PC_TOKEN:
        headers['Authorization'] = 'Bearer ' + PC_TOKEN
    req = Request(PC_URL + path, json.dumps(data, ensure_ascii=False).encode(), headers)
    with urlopen(req, timeout=30) as response:
        return json.load(response)


def scope(user, player):
    key = hashlib.sha256((user + '\0' + player).encode()).hexdigest()
    return pc('/v1/scopes', {'title': '记仇杂货铺 ' + key[:12],
        'summary': '玩家授权保存的虚构游戏经历；不包含真实个人资料。',
        'idempotency_key': 'grudge-shop-v1-' + key})['scope_id']


def history(sid):
    result = pc('/v1/memory/entries/list', {'scope_id': sid, 'limit': 100})
    if result.get('next_cursor'):
        raise ValueError('存档记忆数量超出本应用限制')
    rows = []
    for entry in result['entries']:
        try:
            row = json.loads(entry['text'])
        except (ValueError, KeyError):
            continue
        if row.get('game') == 'grudge-shop-v1':
            rows.append(row)
    rows.sort(key=lambda r: r['turn'])
    refs = sorted([e['artifact'] for e in result['entries']], key=lambda r: r['artifact_id'])
    return rows, refs


def state(rows):
    suspicion = 0
    for row in rows:
        suspicion = max(0, min(5, suspicion + {'prank': 2, 'apologize': -1}.get(row['action'], 0)))
    return {'turn': len(rows), 'suspicion': suspicion, 'price': 3 + suspicion * 2,
            'badge': '老冤家' if suspicion >= 4 else '熟客' if rows else '初来乍到'}


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


def prepare(data):
    user = text(data, 'user', 200)
    player = text(data, 'player', 40)
    action = text(data, 'action', 20)
    item = text(data, 'item', 150)
    rid = text(data, 'request_id', 100)
    if action not in LABELS:
        raise ValueError('不支持的行动')
    sid = scope(user, player)
    rows, ref = history(sid)
    if len(rows) >= 20:
        raise ValueError('本角色已完成 20 回合。请换一个角色存档名开始新故事。')
    before = state(rows)
    after = state(rows + [{'action': action}])
    recalls = '\n'.join(f"第{r['turn']}回合 {LABELS[r['action']]}：{r['item']}" for r in rows[-5:])
    payload = {'scope_id': sid, 'request_id': rid, 'action': action, 'item': item,
               'turn': len(rows) + 1, 'fingerprint': hashlib.sha256(json.dumps(ref, sort_keys=True).encode()).hexdigest(), 'issued': time.time()}
    return {'ticket': signed(payload), 'before': before, 'after': after,
            'memories': recalls or '没有历史记忆。不能假装认识玩家。',
            'action': LABELS[action], 'item': item, 'scope_id': sid,
            'memory_ref': ref, 'memory_count': len(rows)}


def commit(data):
    payload = unpack(text(data, 'ticket', 6000))
    reply = text(data, 'reply', 1400)
    sid = payload['scope_id']
    rows, ref = history(sid)
    for row in rows:
        if row['request_id'] == payload['request_id']:
            return {'saved': True, 'duplicate': True, 'reply': row['reply'], 'state': state(rows), 'memory_ref': ref}
    fingerprint = hashlib.sha256(json.dumps(ref, sort_keys=True).encode()).hexdigest()
    if fingerprint != payload['fingerprint']:
        raise ValueError('同一存档有其他回合已提交，请重新运行，避免覆盖记忆')
    record = {'game': 'grudge-shop-v1', 'turn': payload['turn'], 'request_id': payload['request_id'],
              'action': payload['action'], 'item': payload['item'], 'reply': reply}
    request = {'scope_id': sid, 'kind': 'fact', 'text': json.dumps(record, ensure_ascii=False),
               'reason': '玩家主动参与虚构游戏，保存本回合以便下次互动复用。'}
    saved = pc('/v1/memory/remember', request)
    # Read through PowerContext's supported API before announcing persistence.
    readback, memory_ref = history(sid)
    if not any(r['request_id'] == record['request_id'] for r in readback):
        raise RuntimeError('记忆写入后读回失败')
    return {'saved': True, 'duplicate': False, 'reply': reply, 'state': state(readback),
            'memory_ref': memory_ref, 'write_result': saved}


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
        self.respond(200 if self.path == '/health' else 404, {'service': 'grudge-shop', 'version': '1.0.0'})

    def do_POST(self):
        if not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + SHOP_TOKEN):
            return self.respond(401, {'error': '需要正确的 SHOP_TOKEN'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if size < 1 or size > 20000:
                raise ValueError('请求大小无效')
            data = json.loads(self.rfile.read(size))
            with LOCK:
                if self.path == '/prepare':
                    result = prepare(data)
                elif self.path == '/commit':
                    result = commit(data)
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
