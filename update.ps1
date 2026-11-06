# 一键更新：拉取 ship-it 最新版本
# 用法: .\update.ps1
# 前提: 已通过 git clone 安装本仓库（不是 .skill 解压安装）
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repo

Write-Host "拉取最新版本..." -ForegroundColor Cyan
git pull

if ($LASTEXITCODE -ne 0) {
    Write-Host "拉取失败，请检查网络或是否有本地改动未提交。" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "已更新到最新版本。" -ForegroundColor Green
Write-Host "DSH / Codex 会自动重扫 ~/.agents/skills，无需重启。" -ForegroundColor Green
Write-Host "Claude Code 用户需确认 ~/.claude/skills/ship-it 链接仍指向本仓库。" -ForegroundColor Yellow
Write-Host ""
Write-Host "确认当前版本："
$skillMd = Join-Path $repo 'ship-it\SKILL.md'
if (Test-Path $skillMd) {
    Get-Content $skillMd -TotalCount 5 | Select-String 'version'
}
