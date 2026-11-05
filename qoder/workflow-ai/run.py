"""Run the local PowerContext server and WorkFlow AI together."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')


def powercontext_env(folder, port):
    env = os.environ.copy()
    for key in list(env):
        if key.startswith('POWERCONTEXT_SERVER_'):
            del env[key]
    folder = Path(folder).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    env.update({
        'POWERCONTEXT_SERVER_DATABASE': json.dumps({'kind': 'sqlite', 'url': 'sqlite+aiosqlite:///' + (folder / 'pc.db').as_posix()}),
        'POWERCONTEXT_SERVER_WORKSPACE': str(folder),
        'POWERCONTEXT_SERVER_HTTP_HOST': '127.0.0.1',
        'POWERCONTEXT_SERVER_HTTP_PORT': str(port),
        'POWERCONTEXT_SERVER_MCP_ENABLED': 'false',
    })
    return env


def pc_command():
    cli = Path(sys.executable).parent / ('powercontext.exe' if os.name == 'nt' else 'powercontext')
    return [str(cli), 'server', 'run']


def wait_ready(url, process, seconds=120):
    with httpx.Client(trust_env=False, timeout=2) as client:
        for _ in range(seconds):
            if process.poll() is not None:
                raise RuntimeError(f'服务已退出，exit={process.returncode}；请查看服务日志')
            try:
                if client.get(url).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(1)
    raise RuntimeError(f'等待服务超时: {url}')


def stop(process):
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)


def main():
    processes = []
    pc_port = int(os.getenv('LOCAL_POWERCONTEXT_PORT', '18080'))
    app_port = int(os.getenv('APP_PORT', '8000'))
    pc_url = os.getenv('POWERCONTEXT_SERVER_URL', f'http://127.0.0.1:{pc_port}')
    env = os.environ.copy()
    env['POWERCONTEXT_SERVER_URL'] = pc_url
    try:
        if os.getenv('POWERCONTEXT_EXTERNAL', 'false').lower() != 'true':
            if pc_port == app_port:
                raise SystemExit('应用与 PowerContext 不能使用同一端口')
            if pc_url.rstrip('/') != f'http://127.0.0.1:{pc_port}':
                raise SystemExit('使用远程 PowerContext 时设置 POWERCONTEXT_EXTERNAL=true')
            process = subprocess.Popen(pc_command(), env=powercontext_env(Path(os.getenv('WORKFLOW_PC_DATA', str(ROOT / '.powercontext'))), pc_port), cwd=ROOT)
            processes.append(process)
            wait_ready(pc_url + '/health/ready', process)
        process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'backend.main:app',
                                    '--host', os.getenv('APP_HOST', '127.0.0.1'), '--port', str(app_port)],
                                   env=env, cwd=ROOT)
        processes.append(process)
        wait_ready(f'http://127.0.0.1:{app_port}/api/health', process)
        print(f'WorkFlow AI: http://127.0.0.1:{app_port} （单用户本地运行）', flush=True)
        while all(process.poll() is None for process in processes):
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        for process in reversed(processes):
            stop(process)


if __name__ == '__main__':
    main()
