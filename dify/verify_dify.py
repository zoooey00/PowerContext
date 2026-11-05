"""对发布后的真实 Dify Chatflow 执行三回合，输出真实模型回复。"""
import json
import os
from pathlib import Path
import time
from urllib.request import Request, urlopen
import uuid

url = os.environ.get('DIFY_API_URL', 'http://localhost/v1').rstrip('/')
key = os.environ['DIFY_APP_API_KEY']
user = 'judge-' + uuid.uuid4().hex
rows = []
for query, price, turn in [('恶作剧：会打嗝的月亮', 7, 1), ('交换：一双失眠的拖鞋', 7, 2), ('道歉：一颗薄荷糖', 5, 3)]:
    # 每轮新会话，使用相同 end-user 与 player；不依赖 Dify 的聊天历史。
    payload = {'inputs': {'player': '月亮来客'}, 'query': query, 'response_mode': 'blocking', 'user': user}
    request = Request(url + '/chat-messages', json.dumps(payload, ensure_ascii=False).encode(),
                      {'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    with urlopen(request, timeout=180) as response:
        result = json.load(response)
    answer = result.get('answer', '')
    assert f'第 {turn} 回合' in answer and f'交换价 {price} 枚纽扣' in answer and '记忆已保存' in answer, result
    rows.append({'input': payload, 'result': result})
assert len({r['result']['conversation_id'] for r in rows}) == 3
assert '月亮' in rows[1]['result']['answer'], '第二回合模型未回扣月亮，请检查召回上下文和模型表现'
out = Path(__file__).parent / 'evidence' / 'dify-live.json'
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps({'tested_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'passed': True,
    'scope': 'real Dify published Chatflow API; real provider LLM; 3 distinct conversations', 'runs': rows}, ensure_ascii=False, indent=2), encoding='utf-8')
print('真实 Dify 验收通过：' + str(out))
