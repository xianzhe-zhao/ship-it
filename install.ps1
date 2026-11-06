# 把本仓库的 skills 以 junction 方式接入全局 skill 目录（~/.agents/skills）
# 真源在仓库：改仓库即生效，不产生第二份会漂移的副本
# 用法: .\install.ps1 [-Force]
param([switch]$Force)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
$target = Join-Path $env:USERPROFILE '.agents\skills'
New-Item -ItemType Directory -Path $target -Force | Out-Null

$skills = Get-ChildItem $repo -Directory | Where-Object { Test-Path (Join-Path $_.FullName 'SKILL.md') }
if ($skills.Count -eq 0) { Write-Error "No skill folders (with SKILL.md) found in $repo" }

foreach ($s in $skills) {
  $dest = Join-Path $target $s.Name
  if (Test-Path $dest) {
    if (-not $Force) {
      Write-Host "SKIP  $($s.Name) (already exists; use -Force to replace)" -ForegroundColor Yellow
      continue
    }
    $item = Get-Item $dest -Force
    if (-not $item.LinkType) {
      throw "$dest 是真实目录（不是链接），拒绝删除。请先手动移走，避免误删用户数据。"
    }
    # 只删链接本身，不碰目标目录
    [System.IO.Directory]::Delete($dest, $false)
  }
  New-Item -ItemType Junction -Path $dest -Target $s.FullName | Out-Null
  Write-Host "LINK  $($s.Name) -> $($s.FullName)" -ForegroundColor Green
}
Write-Host "Done. DSH rescans ~/.agents/skills live (no restart needed)."
