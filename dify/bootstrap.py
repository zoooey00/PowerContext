"""python bootstrap.py；需要 Python 3.12 和可访问 PyPI / GitHub 的网络。"""
import os
from pathlib import Path
import subprocess
import sys
import venv

root = Path(__file__).resolve().parent
env_dir = root / '.venv'
if not env_dir.exists():
    venv.create(env_dir, with_pip=True)
python = env_dir / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
env = os.environ.copy()
# GitHub ZIP 不含 git 元数据；源码身份由 URL 中的不可变 commit 锁定。
env['SETUPTOOLS_SCM_PRETEND_VERSION'] = '0.1.0'
subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(root / 'requirements-lock.txt')], env=env, check=True)
subprocess.run([str(python), str(root / 'configure.py')], check=True)
print('安装及本机密钥生成完成。使用虚拟环境的 python run.py 启动。')
