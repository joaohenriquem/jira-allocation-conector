param(
    [string]$msg = ""
)

if (-not $msg) {
    $msg = Read-Host "Mensagem do commit"
}

if (-not $msg) {
    Write-Host "Commit cancelado. Informe uma mensagem." -ForegroundColor Red
    exit 1
}

Write-Host "`n=== Adicionando arquivos ===" -ForegroundColor Cyan
git add -A

Write-Host "`n=== Commit: $msg ===" -ForegroundColor Cyan
git commit -m $msg

Write-Host "`n=== Push para GitHub (origin) ===" -ForegroundColor Green
git push origin main

Write-Host "`n=== Push para GitLab (gitlab) ===" -ForegroundColor Yellow
git push gitlab main

Write-Host "`n=== Concluido ===" -ForegroundColor Cyan
