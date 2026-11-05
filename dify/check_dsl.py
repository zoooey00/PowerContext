"""检查交付 DSL 图、选择器和代码节点；不代替真实 Dify 导入运行。"""
import json
from pathlib import Path
import build_dsl

root = Path(__file__).parent
dsl = json.loads((root / 'grudge-shop.yml').read_text(encoding='utf-8'))
assert dsl == build_dsl.build(), '请重新执行 build_dsl.py'
graph = dsl['workflow']['graph']
nodes = {n['id']: n['data'] for n in graph['nodes']}
assert len(nodes) == len(graph['nodes'])
assert len(graph['edges']) == len(nodes) - 1
for e in graph['edges']:
    assert e['source'] in nodes and e['target'] in nodes
for data in nodes.values():
    for v in data.get('variables', []):
        if isinstance(v, dict) and 'value_selector' in v:
            selector = v['value_selector']
            assert selector[0] in nodes or selector[0] in ('sys', 'env')
    if data['type'] == 'code':
        compile(data['code'], '<DSL code>', 'exec')


def call(nid, **kwargs):
    namespace = {}
    exec(nodes[nid]['code'], namespace)
    return namespace['main'](**kwargs)


for query, action in [('恶作剧：月亮"\n换行', 'prank'), ('交换：拖鞋', 'trade'), ('道歉：薄荷糖', 'apologize'), ('你好', 'look')]:
    value = call('input', user='u', player='p', query=query, request_id='r')
    parsed = json.loads(value['body'])
    assert parsed['action'] == action
for nid in ('parse', 'receipt'):
    try:
        call(nid, body='{}', status_code=503)
        raise AssertionError('服务错误不能输出成功结果')
    except ValueError:
        pass
print('DSL 静态检查通过；实际 Dify 导入和模型执行需另行验证。')
