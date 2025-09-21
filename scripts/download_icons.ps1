<#
.SYNOPSIS
  Lädt Service-Icons von einer vordefinierten Liste herunter.
.DESCRIPTION
  Dieses Skript erstellt einen Ordner 'service-icons' und lädt für jeden Service
  in der Liste das entsprechende Logo herunter. Die Dateien werden automatisch nach dem
  Service benannt (z.B. 'adguard.svg').
#>

# --- Konfiguration ---
# Der Zielordner für die heruntergeladenen Icons.
$targetFolder = ".\service-icons"

# Die Liste der Services und ihrer Icon-URLs.
# Ein leerer String bedeutet, dass kein Icon gefunden wurde und der Service übersprungen wird.
# Die Liste der Services und ihrer Icon-URLs.
# Ein leerer String bedeutet, dass kein offizielles Icon gefunden wurde und der Service übersprungen wird.
$iconUrls = @{
    "2fauth"                 = "https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/svg/2fauth.svg"
    "actual-budget"          = "https://actualbudget.org/static/media/actual.4de29f04.svg" # Hinweis: URL enthält einen Hash und kann sich ändern.
    "adguard"                = "https://adguard.com/images/adguard_logo.svg"
    "adguard-sync"           = "https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/svg/adguard-home-sync.svg"
    "altus"                  = "https://brandfetch.com/asset/0/00A4EB/icon/id45551c6a.svg"
    "apt-cacher-ng"          = "https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/apt-cacher-ng.png" # Inoffizielles Icon aus einer Community-Bibliothek
    "aria2"                  = "https://raw.githubusercontent.com/aria2/aria2.github.io/master/images/aria2_logo.svg"
    "authentik"              = "https://goauthentik.io/img/icon.svg"
    "bedrockconnect"         = "https://github.com/Pugmatt/BedrockConnect/raw/master/media/logo.png"
    "bookstack"              = "https://raw.githubusercontent.com/BookStackApp/BookStack/development/dev/docs/bookstack-logo-icon.svg"
    "cadvisor"               = "https://github.com/google/cadvisor/raw/master/logo.png"
    "checkmk"                = "https://streamlinehq.com/assets/icons/simple-icons/checkmk-hexagon-cube-geometric-modern-abstract-design-shape-art-symbol-graphic.svg"
    "docker-proxy"           = "https://www.docker.com/wp-content/uploads/2022/03/Moby-logo.png" # Moby ist das Open-Source-Projekt hinter Docker
    "docker-to-dns"          = "https://raw.githubusercontent.com/linuxserver/docker-duckdns/master/icon.png" # Beispiel-Icon (DuckDNS), da es kein offizielles Logo gibt
    "dockermon"              = "https://raw.githubusercontent.com/linuxserver/docker-templates/master/linuxserver.io/img/docker-logo.png" # Generisches Docker-Logo
    "emqx"                   = "https://www.emqx.com/en/img/logo-for-white-bg.svg"
    "emulatorjs"             = "https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/svg/emulatorjs.svg"
    "grafana"                = "https://grafana.com/static/img/menu/grafana2.svg"
    "grocy"                  = "https://raw.githubusercontent.com/grocy/grocy/master/public/img/logo.svg"
    "guacamole"              = "https://guacamole.apache.org/images/guacamole-logo-color.svg"
    "headscale"              = "https://dashboardicons.org/headscale.svg"
    "homeassistant"          = "https://www.home-assistant.io/images/home-assistant-logo.svg"
    "homebridge"             = "https://raw.githubusercontent.com/homebridge/branding/main/logos/homebridge-wordmark-logo-horizontal.svg"
    "homepage"               = "https://raw.githubusercontent.com/gethomepage/homepage/main/public/android-chrome-192x192.png"
    "immich"                 = "https://immich.app/img/immich-logo.svg"
    "it-tools"               = "https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/svg/it-tools.svg"
    "jdownloader"            = "https://jdownloader.org/img/logo/jd_logo_256_256.png"
    "linkwarden"             = "https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/linkwarden.png"
    "matter"                 = "https://csa-iot.org/wp-content/uploads/2021/12/matter.svg"
    "music-assistant"        = "https://github.com/music-assistant/server/raw/main/assets/logo.png"
    "n8n"                    = "https://n8n.io/guidelines/logo-dark.svg"
    "netbootxyz"             = "https://netboot.xyz/img/nbxyz-transparent-logo-black.png"
    "netbox"                 = "https://www.dashboardicons.com/icons/netbox-full.svg"
    "network-master"         = "https://www.ceragon.com/hubfs/Ceragon_December2021/images/logo.svg" # Logo des Herstellers (Ceragon)
    "nextcloud"              = "https://nextcloud.com/c/uploads/2022/08/nextcloud-logo-icon.svg"
    "nodered"                = "https://nodered.org/about/resources/media/node-red-icon.svg"
    "openweb-ui"             = "https://www.dashboardicons.com/icons/open-webui/dark.svg"
    "pairdrop"               = "https://github.com/schlagmichdoch/PairDrop/raw/master/public/images/android-chrome-512x512.png"
    "paperless-ngx"          = "https://streamlinehq.com/assets/icons/simple-icons/paperlessngx-communication-logo.svg"
    "peppermint"             = "https://raw.githubusercontent.com/Peppermint-Lab/peppermint/main/public/images/logo-light.svg"
    "photoprism"             = "https://dl.photoprism.app/img/logo/logo.svg"
    "plex"                   = "https://www.plex.tv/wp-content/uploads/2018/01/pmp-icon-1.png"
    "prometheus"             = "https://prometheus.io/_next/static/media/prometheus-logo.7aa022e5.svg" # Hinweis: URL enthält einen Hash und kann sich ändern.
    "roundcube"              = "https://upload.wikimedia.org/wikipedia/commons/e/e3/Roundcube_logo_icon.svg"
    "scrypted"               = "https://github.com/koush/scrypted/raw/main/plugins/prebuffer/web/public/logo.svg"
    "semaphore"              = "https://semaphoreui.com/img/semaphore-dark.png"
    "sinusbot"               = "https://raw.githubusercontent.com/SinusBot/sinusbot.github.io/master/sinusbot-logo.svg"
    "stash"                  = "https://raw.githubusercontent.com/stashapp/stash/develop/ui/v2.0/src/assets/images/stash-logo.svg"
    "syncthing"              = "https://syncthing.net/img/logo-horizontal.svg"
    "technitum"              = "" # Kein Softwareprojekt, sondern ein chemisches Element. Kein Logo verfügbar.
    "traccar"                = "https://www.traccar.org/images/logo.svg"
    "traefik"                = "https://traefik.io/logos/traefik-proxy-logo-dark.svg"
    "uptime"                 = "https://raw.githubusercontent.com/louislam/uptime-kuma/master/public/icon.svg"
    "vaultwarden"            = "https://upload.wikimedia.org/wikipedia/commons/4/44/Vaultwarden_logo.svg"
    "vikunja"                = "https://vikunja.io/assets/img/logo.svg"
    "vscode"                 = "https://code.visualstudio.com/apple-touch-icon.png"
    "wastebin"               = "" # Generischer Begriff für eine Softwarekategorie, kein spezifisches Projekt mit Logo.
    "watchtower"             = "https://github.com/containrrr/watchtower/raw/main/logo.png"
    "webgrab"                = "https://raw.githubusercontent.com/linuxserver/docker-templates/master/linuxserver.io/img/webgrabplus-logo.png" # Alias für WebGrab+Plus
    "webtop"                 = "https://raw.githubusercontent.com/linuxserver/docker-templates/master/linuxserver.io/img/webtop-logo.png"
    "wikijs"                 = "https://js.wiki/img/wikijs-full-2021.b840e376.svg" # Hinweis: URL enthält einen Hash und kann sich ändern.
    "youtube-dl"             = "https://raw.githubusercontent.com/ytdl-org/youtube-dl/master/youtube_dl/favicon.svg"
    "zigbee2mqtt"            = "https://www.zigbee2mqtt.io/logo.png"
    "bgutil-pot"             = "https://lib.rs/assets/cargo.png" # Generisches Icon für eine Rust-Crate
    "carconnectivity-mqtt"   = "https://carconnectivity.org/wp-content/uploads/2021/05/CCC-Logo-Full-Color.svg" # Logo der übergeordneten Organisation
    "openwakeword"           = "https://github.com/rhasspy/openWakeWord-cpp/raw/master/img/logo.png"
}
# --- Skriptlogik ---

# Prüfen, ob der Zielordner existiert, andernfalls erstellen.
if (-not (Test-Path -Path $targetFolder)) {
    Write-Host "📂 Erstelle Ordner: $targetFolder" -ForegroundColor Yellow
    New-Item -Path $targetFolder -ItemType Directory | Out-Null
} else {
    Write-Host "📂 Ordner '$targetFolder' existiert bereits."
}

# Schleife durch die Liste der Icons.
foreach ($entry in $iconUrls.GetEnumerator()) {
    $serviceName = $entry.Name
    $url = $entry.Value

    # Überspringe Einträge ohne URL.
    if ([string]::IsNullOrWhiteSpace($url)) {
        Write-Host "🚫 Überspringe '$serviceName' (keine URL)." -ForegroundColor Gray
        continue
    }

    try {
        # Extrahiere die Dateiendung aus der URL.
        $fileExtension = [System.IO.Path]::GetExtension($url.Split('?')[0])
        if ([string]::IsNullOrWhiteSpace($fileExtension)) { $fileExtension = ".png" } # Standard-Endung, falls keine gefunden wird.
        
        $fileName = "$serviceName$fileExtension"
        $filePath = Join-Path -Path $targetFolder -ChildPath $fileName

        Write-Host "⬇️  Lade Icon für '$serviceName'..." -ForegroundColor Cyan
        
        # Lade die Datei herunter.
        Invoke-WebRequest -Uri $url -OutFile $filePath -UseBasicParsing
        
        Write-Host "✔️  Gespeichert als '$filePath'" -ForegroundColor Green
    }
    catch {
        Write-Host "🔥 Fehler beim Herunterladen von '$serviceName' von URL '$url'." -ForegroundColor Red
        Write-Host $_.Exception.Message -ForegroundColor Red
    }
}

Write-Host "✨ Download-Vorgang abgeschlossen." -ForegroundColor Magenta