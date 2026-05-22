# Dokumentation: aac-hugo

## 1. Service-Übersicht

* **Beschreibung:** Static Site Generator & Development Server
* **Kategorie:** Documentation
* **Hostname:** `hugo.int.fam-feser.de`
* **Docker Image:** `hugomods/hugo:debian-go-git`

---

## 2. Deployment-Konfiguration

Die folgenden Konfigurationsdateien werden automatisch von der AAC Template Engine basierend auf der `service.yml` generiert.

### 2.1 Docker Compose (`docker-compose.yml`)

Diese Datei definiert den Hauptservice und seine Abhängigkeiten wie Datenbanken oder Redis.

```yaml
volumes:
- site:/src/site
- config:/config
- local_time:/etc/localtime
networks_to_join: []
restart_policy: unless-stopped
host_base_path: /export/docker
command:
- /bin/sh
- -c
- chmod +x /config/clone_repo.sh && /config/clone_repo.sh && exec hugo server --disableFastRender
  --source /src/site --destination /public --bind=0.0.0.0 --port 1313 --appendPort=false
  --baseURL https://hugo.int.fam-feser.de

```

### 2.2 Nicht-geheime Umgebungsvariablen (`.env`)

Diese Variablen enthalten allgemeine Konfigurationen und sind nicht als geheim eingestuft.

```ini
PUID="1000"
TZ="Europe/Berlin"
PGID="1000"
GIT_REPO_URL="https://gitlab.int.fam-feser.de/documentation/aac-iac-documentation.git"
```

---

## 3. Volumes und Datenhaltung

Persistente Daten für diesen Service werden auf dem Host-System unter folgendem Basispfad gespeichert: `/export/docker/aac-hugo`.

Definierte Mount-Pfade und Berechtigungen:

* **Host-Pfad:** `/export/docker/aac-hugo`
  * **Besitzer (UID):** `1000`
  * **Gruppe (GID):** `1000`
* **Host-Pfad:** `/export/docker/aac-hugo/site`
  * **Besitzer (UID):** `1000`
  * **Gruppe (GID):** `1000`
* **Host-Pfad:** `/export/docker/aac-hugo/config`
  * **Besitzer (UID):** `1000`
  * **Gruppe (GID):** `1000`
* **Host-Pfad:** `/etc/localtime`
  * **Besitzer (UID):** `1000`
  * **Gruppe (GID):** `1000`

---

## 4. Integrationen

* **Homepage Dashboard:** `Aktiviert`
* **Automatische DNS-Erstellung:** `Aktiviert`
