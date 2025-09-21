<#
.SYNOPSIS
  Erstellt automatisch GitLab-Projekte basierend auf einer vordefinierten Liste.
.DESCRIPTION
  Dieses Skript verwendet eine feste Liste von Projektnamen und führt für jeden Namen
  das Python-Skript 'pipeline_create_repo.py' mit den entsprechenden Parametern aus.
#>

# --- Konfiguration ---
# Hier kannst du alle deine Standardwerte anpassen.

$repoPrefix = "aac-"
$groupPath = "aac-application-definitions"
$templatePath = "aac-application-definitions/templates/aac-template-application-projekt"
$webhookSourcePath = "aac-application-definitions/aac-template-engine"
$gitlabUrl = "https://gitlab.int.fam-feser.de"
$branches = "dev,test,main,prod"
$templateTriggerBranch = "main"
$targetTriggerBranch = "dev"

# --- Feste Projektliste ---
# Anstatt Ordner zu lesen, verwendet das Skript diese Liste.

$projectNamesList = @(
    "2fauth",
    "actual-budget",
    "adguard",
    "adguard-sync",
    "altus",
    "apt-cacher-ng",
    "aria2",
    "authentik",
    "bedrockconnect",
    "bookstack",
    "cadvisor",
    "checkmk",
    "docker-proxy",
    "docker-to-dns",
    "dockermon",
    "emqx",
    "emulatorjs",
    "grafana",
    "grocy",
    "guacamole",
    "headscale",
    "homeassistant",
    "homebridge",
    "homepage",
    "immich",
    "it-tools",
    "jdownloader",
    "linkwarden",
    "matter",
    "music-assistant",
    "n8n",
    "netbootxyz",
    "netbox",
    "network-master",
    "nextcloud",
    "nodered",
    "openweb-ui",
    "pairdrop",
    "paperless-ngx",
    "peppermint",
    "photoprism",
    "plex",
    "prometheus",
    "roundcube",
    "scrypted",
    "semaphore",
    "sinusbot",
    "stash",
    "syncthing",
    "technitum",
    "traccar",
    "traefik",
    "uptime",
    "vaultwarden",
    "vikunja",
    "vscode",
    "wastebin",
    "watchtower",
    "webgrab",
    "webtop",
    "wikijs",
    "youtube-dl",
    "zigbee2mqtt",
    "bgutil-pot-server",
    "carconnectivity-mqtt",
    "openwakeword"
)

# --- Skriptlogik ---

Write-Host "📝 Lade vordefinierte Projektliste..."
Write-Host "✔️ Es wurden $($projectNamesList.Count) Projekte in der Liste gefunden."

# Schleife durch jeden Namen in der Liste
foreach ($projectName in $projectNamesList) {
    # Baue den vollständigen Repository-Namen zusammen
    $repoName = "$repoPrefix$projectName"

    Write-Host "------------------------------------------------------------"
    Write-Host "🚀 Starte Erstellung für Repository: $repoName" -ForegroundColor Cyan
    Write-Host "------------------------------------------------------------"

    # Rufe das Python-Skript mit den korrekten Parametern auf
    try {
        py pipeline_create_repo.py `
            --repo-name $repoName `
            --group-path $groupPath `
            --template-path $templatePath `
            --webhook-source-path $webhookSourcePath `
            --gitlab-url $gitlabUrl `
            --branches $branches `
            --template-trigger-branch $templateTriggerBranch `
            --target-trigger-branch $targetTriggerBranch
        
        Write-Host "✅ Erfolgreich für $repoName abgeschlossen." -ForegroundColor Green
    }
    catch {
        Write-Host "🔥 Fehler bei der Erstellung von $repoName. Siehe Ausgabe oben." -ForegroundColor Red
    }
}

Write-Host "------------------------------------------------------------"
Write-Host "✨ Alle Projekte aus der Liste wurden verarbeitet." -ForegroundColor Magenta