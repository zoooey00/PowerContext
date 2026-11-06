"""静态图与导出一致性检查，不冒充实际云端运行。"""
import json
from pathlib import Path
import build_dsl
root=Path(__file__).parent
dsl=json.loads((root/'grudge-shop.yml').read_text(encoding='utf-8'))
assert dsl==build_dsl.build()
g=dsl['workflow']['graph']; nodes={n['id']:n['data'] for n in g['nodes']}
assert len(nodes)==11 and len(g['edges'])==10
for edge in g['edges']:
    assert edge['source'] in nodes and edge['target'] in nodes
for node in nodes.values():
    if node['type']=='code':compile(node['code'],'<Dify code>','exec')
    for v in node.get('variables',[]):
        if isinstance(v,dict) and 'value_selector' in v:
            assert v['value_selector'][0] in nodes or v['value_selector'][0] in ['sys','env']
assert nodes['gate']['type']=='if-else'
assert any(e['source']=='gate' and e['target']=='limit' and e['sourceHandle']=='false' for e in g['edges'])
assert nodes['npc']['prompt_template'][1]['text']=='结构化状态：{{#settle.context#}}'
print('11节点/10边；规则源码已嵌入；上限分支及引用静态检查通过')
