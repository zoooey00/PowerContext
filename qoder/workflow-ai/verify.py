"""Real HTTP integration test with fresh databases and actual PowerContext processes."""
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
import tempfile
from datetime import date, timedelta, datetime, timezone
from run import powercontext_env, pc_command, wait_ready, stop
import httpx

ROOT = Path(__file__).resolve().parent


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def main():
    output = ROOT / 'evidence'
    output.mkdir(exist_ok=True)
    result = {'tested_at': datetime.now(timezone.utc).isoformat(), 'passed': False, 'checks': [],
              'environment': {'python': platform.python_version(), 'os': platform.platform(),
                  'dependencies': {name: importlib.metadata.version(name) for name in
                                   ['fastapi','httpx','aiosqlite','pydantic','uvicorn','python-dotenv','powercontext']}},
              'scope': 'Actual PowerContext HTTP and WorkFlow AI HTTP; FTS, no LLM, no mock',
              'steps': []}
    distribution = importlib.metadata.distribution('powercontext')
    result['environment']['powercontext_source'] = json.loads(distribution.read_text('direct_url.json') or '{}')
    processes = []
    with tempfile.TemporaryDirectory(prefix='workflow-ai-') as folder, open(output / 'services.log', 'w', encoding='utf-8') as logs:
        pc_port, app_port = free_port(), free_port()
        pc_url, app_url = f'http://127.0.0.1:{pc_port}', f'http://127.0.0.1:{app_port}'
        app_env = os.environ.copy()
        app_env.update({'DATABASE_PATH': str(Path(folder) / 'workflow.db'), 'POWERCONTEXT_SERVER_URL': pc_url,
                        'POWERCONTEXT_SCOPE_ID': '', 'POWERCONTEXT_SCOPE_KEY': 'workflow-ai-verification',
                        'POWERCONTEXT_SEARCH_MODE': 'fts', 'POWERCONTEXT_API_TOKEN': ''})
        def start_pc():
            process = subprocess.Popen(pc_command(), env=powercontext_env(Path(folder) / 'pc', pc_port),
                                       cwd=folder, stdout=logs, stderr=logs)
            processes.append(process)
            wait_ready(pc_url + '/health/ready', process)
            return process
        def start_app():
            process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'backend.main:app',
                                        '--host','127.0.0.1','--port',str(app_port)], env=app_env, cwd=ROOT,
                                       stdout=logs, stderr=logs)
            processes.append(process)
            wait_ready(app_url + '/api/health', process)
            return process
        try:
            pc = start_pc()
            app = start_app()
            with httpx.Client(base_url=app_url, timeout=30, trust_env=False) as client:
                def request(method, path, expected=200, **kwargs):
                    response = client.request(method, path, **kwargs)
                    assert response.status_code == expected, (path, response.status_code, response.text)
                    payload = response.json()
                    result['steps'].append({'method': method, 'path': path, 'status': response.status_code, 'response': payload})
                    return payload
                health = request('GET','/api/health')
                assert health['powercontext']['status'] == 'healthy'
                assert client.get('/').status_code == 200
                assert client.get('/static/app.js').status_code == 200
                today = date.today().isoformat()
                previous = (date.today()-timedelta(days=1)).isoformat()
                first = request('POST','/api/work-logs', json={'title':'完成登录模块','content':'实现 JWT 认证和登录页面',
                                                              'category':'development','tags':['JWT'],'date':today})
                second = request('POST','/api/work-logs', json={'title':'技术讨论','content':'确定数据库迁移方案',
                                                               'category':'meeting','tags':['数据库'],'date':previous})
                assert first['memory_ref'] and second['memory_ref']
                result['checks'].append('actual memory writes return exact artifact references')
                found = request('GET','/api/search',params={'query':'JWT'})
                assert len(found)==1 and found[0]['id']==first['id'] and found[0]['memory_ref']==first['memory_ref']
                request('POST','/api/search',params={'query':'JWT'})
                result['checks'].append('GET and POST search use real PowerContext hits')
                with httpx.Client(timeout=30, trust_env=False) as fresh:
                    recalled = fresh.get(app_url+'/api/search', params={'query':'JWT'}).json()
                    assert recalled[0]['memory_ref']==first['memory_ref']
                result['checks'].append('new HTTP client recalls the same persisted memory')
                report = request('POST','/api/weekly-report',json={'start_date':previous,'end_date':today,'style':'professional'})
                assert report['statistics']['active_days']==2 and report['statistics']['total_logs']==2
                assert len(report['memory_evidence'])==2 and 'JWT' in report['report']
                assert report['memory_context']['status']=='ready' and report['memory_context']['content']
                compact = request('POST','/api/weekly-report',json={'start_date':previous,'end_date':today,'style':'detailed'})
                assert compact['report'] != report['report']
                result['checks'].append('report uses recalled content and citations; context prepared; two-category days correct')
                chat = request('POST','/api/chat',json={'question':'JWT'})
                assert 'JWT' in chat['answer'] and chat['sources'][0]['memory_ref']==first['memory_ref']
                result['checks'].append('chat answer and sources use real recalled memory')
                request('POST','/api/weekly-report',expected=422,json={'start_date':today,'end_date':previous})
                request('POST','/api/work-logs',expected=422,json={'title':'','content':'invalid'})
                result['checks'].append('invalid dates, reversed range, and empty title rejected')
                # Stop and restart both actual servers, keeping only their databases.
                stop(app); stop(pc)
                pc = start_pc(); app = start_app()
                persisted = request('GET','/api/search',params={'query':'JWT'})
                assert persisted[0]['memory_ref']==first['memory_ref']
                result['checks'].append('both servers restart and recall the same memory from disk')
                updated = request('PUT',f'/api/work-logs/{first["id"]}',json={'content':'完成 OAuth2 集成','tags':['OAuth2']})
                assert updated['memory_ref'] != first['memory_ref']
                assert request('GET','/api/search',params={'query':'JWT'})==[]
                assert request('GET','/api/search',params={'query':'OAuth2'})[0]['id']==first['id']
                request('DELETE',f'/api/work-logs/{first["id"]}')
                assert request('GET','/api/search',params={'query':'OAuth2'})==[]
                result['checks'].append('update retires old memory and deletion removes active recall')
                with httpx.Client(base_url=pc_url, timeout=30, trust_env=False) as upstream:
                    other = upstream.post('/v1/scopes',json={'title':'isolation','summary':'test isolation','idempotency_key':'workflow-ai-other'}).json()
                    isolated = upstream.post('/v1/memory/search',json={'scope_id':other['scope_id'],'query':'workflowlog','limit':10}).json()
                    assert isolated['hits']==[]
                result['checks'].append('different Scope cannot recall this project memory')
                stop(pc)
                request('GET','/api/search',expected=502,params={'query':'JWT'})
                request('POST','/api/work-logs',expected=502,json={'title':'应失败','content':'不可伪装保存成功'})
                remaining = request('GET','/api/work-logs')
                assert len(remaining)==1 and remaining[0]['id']==second['id']
                result['checks'].append('PowerContext offline returns 502 and rolls back local insert; no fake fallback')
                result['passed']=True
        except Exception as error:
            result['error']=str(error)
            raise
        finally:
            for process in reversed(processes):
                stop(process)
            (output / 'integration.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps({'passed':result['passed'],'checks':len(result['checks']),'evidence':str(output/'integration.json')},ensure_ascii=False),flush=True)


if __name__ == '__main__':
    main()
