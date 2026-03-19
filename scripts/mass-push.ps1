$applicationsPath = "C:\Users\Shared\Workdirektory\Code-Infra\GitLab\aac-application-defenitions\applications"
$commitMessage = "feat: migrate to titanium modular engine v2 and cleaned manifests"

Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "🚀 STARTING MASS PUSH FOR ALL APPLICATIONS" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan

# Get all directories inside the applications folder
$repos = Get-ChildItem -Path $applicationsPath -Directory

foreach ($repo in $repos) {
    $repoPath = $repo.FullName
    Write-Host "`nProcessing: $($repo.Name)" -ForegroundColor Yellow
    
    Set-Location $repoPath
    
    # Check if it's actually a git repository
    if (Test-Path ".git") {
        # 1. Switch to dev branch and pull latest just in case
        Write-Host "  -> Switching to dev branch..." -ForegroundColor DarkGray
        git checkout dev 2>&1 | Out-Null
        
        # 2. Add all local changes (the butchered files, .env updates, etc.)
        git add .
        
        # 3. Check if there are actually changes to commit
        $status = git status --porcelain
        if ($status) {
            Write-Host "  -> Committing changes..." -ForegroundColor DarkGray
            git commit -m $commitMessage 2>&1 | Out-Null
            
            Write-Host "  -> Pushing to origin dev..." -ForegroundColor DarkGray
            git push origin dev
            Write-Host "  [SUCCESS] Pushed!" -ForegroundColor Green
        } else {
            Write-Host "  [SKIPPED] No changes to commit." -ForegroundColor DarkGray
        }
    } else {
        Write-Host "  [ERROR] Not a git repository." -ForegroundColor Red
    }
}

Write-Host "`n======================================================" -ForegroundColor Cyan
Write-Host "✅ MASS PUSH COMPLETE." -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan