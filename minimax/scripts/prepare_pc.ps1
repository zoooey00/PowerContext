$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
python scripts/fetch_pc.py
if ($LASTEXITCODE -ne 0) { throw 'Download failed' }
$pcEnvironment = if ($env:PC_VENV) { $env:PC_VENV } else { Join-Path $projectRoot 'runtime/pc-venv' }
python -m venv $pcEnvironment
if ($LASTEXITCODE -ne 0) { throw 'venv failed' }
$env:SETUPTOOLS_SCM_PRETEND_VERSION = '1.4.0+git.2853ed98'
$archiveUri = ([System.Uri](Join-Path $projectRoot 'runtime/powercontext.zip')).AbsoluteUri
& "$pcEnvironment/Scripts/python.exe" -m pip install --no-compile "powercontext[cli,server] @ $archiveUri"
if ($LASTEXITCODE -ne 0) { throw 'Install failed' }
