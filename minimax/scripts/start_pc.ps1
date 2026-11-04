$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$env:POWERCONTEXT_SERVER_DATABASE_KIND = 'sqlite'
$env:POWERCONTEXT_SERVER_DATABASE_URL = 'sqlite+aiosqlite:///./runtime/powercontext.db'
$pcEnvironment = if ($env:PC_VENV) { $env:PC_VENV } else { Join-Path $projectRoot 'runtime/pc-venv' }
& "$pcEnvironment/Scripts/python.exe" -c 'from powercontext.cli.app import main; main()' server run --host 127.0.0.1 --port 8000 --no-env-file
