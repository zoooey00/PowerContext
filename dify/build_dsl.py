"""生成包含全部核心规则的 Dify Chatflow。"""
import inspect
import json
from pathlib import Path
import game_nodes
ROOT = Path(__file__).parent

def code(title, source, variables, outputs):
    return {'type': 'code', 'title': title, 'code_language': 'python3', 'code': source,
            'variables': [{'variable': k, 'value_selector': v} for k, v in variables.items()],
            'outputs': {k: {'type': 'string', 'children': None} for k in outputs}}


def http(title, path, selector):
    return {'type': 'http-request', 'title': title, 'method': 'post',
            'url': '{{#env.SHOP_URL#}}' + path,
            'authorization': {'type': 'no-auth'},
            'headers': 'Content-Type:application/json\nAuthorization:Bearer {{#env.SHOP_TOKEN#}}',
            'params': '', 'body': {'type': 'json', 'data': [{'key': '', 'type': 'text', 'value': selector}]},
            'timeout': {'connect': 10, 'read': 60, 'write': 30}, 'ssl_verify': True,
            'retry_config': {'retry_enabled': False, 'max_retries': 0, 'retry_interval': 1000}}



def source(fn):
    return inspect.getsource(fn).replace('def '+fn.__name__+'(', 'def main(', 1)


def build():
    fields = [{'variable': 'player', 'label': '虚构存档名', 'type': 'text-input', 'required': True, 'max_length': 40, 'options': []},
              {'variable': 'save_code', 'label': '存档随机口令（24–128字；勿用真实密码）', 'type': 'text-input', 'required': True, 'max_length': 128, 'options': []}]
    defs = [
      ('start', {'type':'start','title':'进入纸箱精小店','variables':fields}),
      ('input',code('校验口令与解析行动',source(game_nodes.input_node),{'player':['start','player'],'save_code':['start','save_code'],'query':['sys','query'],'request_id':['sys','workflow_run_id']},['body','command'])),
      ('recall',http('PowerContext 只读事件','/memory/read','{{#input.body#}}')),
      ('settle',code('Dify 规则引擎：重放与结算',source(game_nodes.settle_node),{'body':['recall','body'],'status_code':['recall','status_code'],'command':['input','command']},['allowed','ticket','event','history','context','before','limit_message'])),
      ('gate',{'type':'if-else','title':'Dify 回合上限判断','cases':[{'case_id':'play','logical_operator':'and','conditions':[{'id':'limit','variable_selector':['settle','allowed'],'varType':'string','comparison_operator':'is','value':'yes'}]}]}),
      ('npc',{'type':'llm','title':'模型选择阿扣的语气','model':{'provider':'langgenius/deepseek/deepseek','name':'deepseek-flash','mode':'chat','completion_params':{'temperature':0.5,'max_tokens':100,'thinking':False}},'prompt_template':[{'id':'system','role':'system','text':'你是纸箱精掌柜的情绪导演。仅返回 JSON，格式 {"tone":"astonished"}。tone 只能是 astonished、stern、soft。恶作剧倾向惊讶，警惕高倾向严肃，道歉倾向心软。不得叙述剧情或添加字段。'},{'id':'user','role':'user','text':'结构化状态：{{#settle.context#}}'}],'context':{'enabled':False,'variable_selector':[]},'vision':{'enabled':False},'memory':None}),
      ('render',code('Dify 生成事实台账与校验模型输出',source(game_nodes.render_node),{'ticket':['settle','ticket'],'event':['settle','event'],'history':['settle','history'],'model':['npc','text']},['body','answer','model_guard'])),
      ('save',http('PowerContext 追加并读回','/memory/append','{{#render.body#}}')),
      ('receipt',code('Dify 核对持久化收据',source(game_nodes.receipt_node),{'body':['save','body'],'status_code':['save','status_code'],'answer':['render','answer']},['answer'])),
      ('answer',{'type':'answer','title':'展示本轮结果','answer':'{{#receipt.answer#}}','variables':[]}),
      ('limit',{'type':'answer','title':'存档完结不写入','answer':'{{#settle.limit_message#}}','variables':[]})]
    nodes=[]
    for i,(nid,d) in enumerate(defs):
        d.update(desc='',selected=False)
        pos={'x':i*330,'y':500 if nid=='limit' else 200}
        nodes.append({'id':nid,'type':'custom','position':pos,'positionAbsolute':pos,'width':244,'height':110,'sourcePosition':'right','targetPosition':'left','data':d})
    types={nid:d['type'] for nid,d in defs}
    links=[('start','input','source'),('input','recall','source'),('recall','settle','source'),('settle','gate','source'),('gate','npc','play'),('gate','limit','false'),('npc','render','source'),('render','save','source'),('save','receipt','source'),('receipt','answer','source')]
    edges=[{'id':a+'-'+b,'type':'custom','source':a,'target':b,'sourceHandle':h,'targetHandle':'target','data':{'sourceType':types[a],'targetType':types[b],'isInIteration':False}} for a,b,h in links]
    return {'kind':'app','version':'0.7.0','dependencies':[{'current_identifier':None,'type':'marketplace','value':{'marketplace_plugin_unique_identifier':'langgenius/deepseek:0.0.26@bdf47cb41e9062bba00d26625d2a795c1874011d8ce64bff738c44b5a31787ea','version':None}}],
      'app':{'name':'记仇杂货铺','description':'Dify 内置规则、分支与准确事件账本的跨会话小游戏','mode':'advanced-chat','icon':'📦','icon_background':'#FDE9D0','use_icon_as_answer_icon':False},
      'workflow':{'conversation_variables':[],'environment_variables':[{'id':'shop-url','name':'SHOP_URL','value':'http://host.docker.internal:8099','value_type':'string','description':'运行 configure.py 自动绑定'},{'id':'shop-token','name':'SHOP_TOKEN','value':'','value_type':'secret','description':'运行 configure.py 自动生成并注入'}],
      'features':{'opening_statement':'输入同一虚构存档名及随机口令继续游戏。发送「恶作剧：会打嗝的月亮」「交换：一双失眠的拖鞋」「道歉：薄荷糖」。最多20回合，规则由 Dify 结算。请勿输入真实个人信息。','suggested_questions':['恶作剧：会打嗝的月亮','交换：一双失眠的拖鞋','道歉：薄荷糖'],'suggested_questions_after_answer':{'enabled':False},'speech_to_text':{'enabled':False},'text_to_speech':{'enabled':False,'language':'','voice':''},'retriever_resource':{'enabled':False},'sensitive_word_avoidance':{'enabled':False},'file_upload':{'enabled':False}},'graph':{'nodes':nodes,'edges':edges,'viewport':{'x':0,'y':0,'zoom':0.5}}}}

if __name__ == '__main__':
    data=json.dumps(build(),ensure_ascii=False,indent=2)+'\n'
    (ROOT/'grudge-shop.yml').write_text(data,encoding='utf-8')
    (ROOT/'grudge-shop-cloud.yml').write_text(data,encoding='utf-8')
    import hashlib, zipfile
    content=data.encode('utf-8')
    manifest={'format':'dify.app','format_version':1,'apps':[{'path':'app.yaml','size':len(content),'sha256':hashlib.sha256(content).hexdigest()}]}
    with zipfile.ZipFile(ROOT/'grudge-shop.dify','w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('manifest.yaml',json.dumps(manifest)); z.writestr('app.yaml',content)
