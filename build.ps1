# 从源码构建 .skill 打包文件（输出到 dist\）
# 用法: .\build.ps1
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
$dist = Join-Path $repo 'dist'
New-Item -ItemType Directory -Path $dist -Force | Out-Null

# 优先用 DSH 内置 Python，否则用 PATH 中的 python
$candidate = Join-Path $env:USERPROFILE '.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'
$py = if (Test-Path $candidate) { $candidate } else { 'python' }

# 用 skill-creator 的打包器（本仓库不含 skill-creator，从作者的 Agent-Dev-Release-Workflow 取，或用任意已装的 skill-creator）
$packager = Join-Path $env:USERPROFILE '.agents\skills\skill-creator'
if (-not (Test-Path $packager)) {
    Write-Host "未找到 skill-creator（打包器来源）。请先安装 skill-creator，或手动 zip ship-it 目录。" -ForegroundColor Yellow
    Write-Host "手动替代：Compress-Archive -Path ship-it\* -DestinationPath dist\ship-it.zip，再改后缀为 .skill" -ForegroundColor Yellow
    exit 1
}

Set-Location $packager
& $py -m scripts.package_skill (Join-Path $repo 'ship-it') $dist
Write-Host "Done:"
Get-ChildItem $dist -Filter *.skill | ForEach-Object { Write-Host "  $($_.Name) ($($_.Length) bytes)" }
