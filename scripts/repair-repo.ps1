$applicationsPath = "C:\Users\Shared\Workdirektory\Code-Infra\GitLab\aac-application-defenitions\applications"

Write-Host "[START] FIXING REJECTED PUSHES (GIT SYNC)" -ForegroundColor Cyan

$repos = Get-ChildItem -Path $applicationsPath -Directory

foreach ($repo in $repos) {
    Set-Location $repo.FullName
    
    if (Test-Path ".git") {
        git fetch origin dev 2>&1 | Out-Null
        $status = git status
        
        if ($status -match "diverged" -or $status -match "behind") {
            Write-Host "Fixing sync for: $($repo.Name)" -ForegroundColor Yellow
            
            git pull origin dev --rebase 2>&1 | Out-Null
            git push origin dev 2>&1 | Out-Null
            
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  [SUCCESS] Synced and Pushed!" -ForegroundColor Green
            } else {
                Write-Host "  [ERROR] Manual fix required." -ForegroundColor Red
            }
        }
    }
}

Write-Host "[DONE] FIX COMPLETE." -ForegroundColor Cyan