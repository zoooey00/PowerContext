"""Install the tested application and fixed official PowerContext source into .venv."""
import os
from pathlib import Path
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent
if sys.version_info < (3, 11):
    raise SystemExit('需要 Python 3.11+，本次实测 3.12.16')
python = ROOT / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
if not python.exists():
    venv.EnvBuilder(with_pip=True).create(ROOT / '.venv')
subprocess.check_call([str(python), '-m', 'pip', 'install', '-r', str(ROOT / 'requirements.txt')])
env = os.environ.copy()
# Official source ZIP omits Git metadata. This labels distribution metadata only.
env['SETUPTOOLS_SCM_PRETEND_VERSION'] = '0.1.0'
subprocess.check_call([str(python), '-m', 'pip', 'install',
    'powercontext[cli,server] @ https://github.com/oceanbase/powercontext/archive/c4b9b540a6daa6514be83f1696e0fccf18c5c147.zip'], env=env)
print('安装完成。Windows: .venv\\Scripts\\python.exe run.py；Linux/macOS: .venv/bin/python run.py')
