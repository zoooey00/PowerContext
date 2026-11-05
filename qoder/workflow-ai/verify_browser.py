"""Isolated browser QA against real local services."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import json
from run import ROOT, stop, wait_ready
from verify import free_port

def main():
    evidence = ROOT / 'evidence'
    processes = []
    with tempfile.TemporaryDirectory(prefix='workflow-ui-') as folder, open(evidence/'ui-services.log','w',encoding='utf-8') as log:
        port, pc_port = free_port(), free_port()
        env=os.environ.copy()
        env.update({'APP_PORT':str(port),'LOCAL_POWERCONTEXT_PORT':str(pc_port),
                    'POWERCONTEXT_SERVER_URL':f'http://127.0.0.1:{pc_port}',
                    'POWERCONTEXT_SCOPE_KEY':'workflow-ai-browser-check','DATABASE_PATH':str(Path(folder)/'work.db'),
                    'POWERCONTEXT_SCOPE_ID':'','POWERCONTEXT_EXTERNAL':'false'})
        # run.py stores local PowerContext in its own project path; use an isolated override.
        env['WORKFLOW_PC_DATA']=str(Path(folder)/'pc')
        try:
            app=subprocess.Popen([sys.executable,str(ROOT/'run.py')],env=env,cwd=ROOT,stdout=log,stderr=log)
            processes.append(app)
            wait_ready(f'http://127.0.0.1:{port}/api/health',app)
            subprocess.check_call(['node',str(ROOT/'scripts'/'browser-check.mjs'),'app',f'http://127.0.0.1:{port}',str(evidence)],cwd=ROOT)
        finally:
            # Terminate the process tree belonging only to this isolated run.
            for process in reversed(processes):
                if os.name=='nt' and process.poll() is None:
                    subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                    process.wait(timeout=20)
                else:
                    stop(process)

if __name__=='__main__':
    main()
