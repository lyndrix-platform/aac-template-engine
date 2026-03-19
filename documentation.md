# AAC Template Engine Dokumentation

## 1. Übersicht

Die AAC Template Engine ist ein GitOps-Framework, das darauf ausgelegt ist, die Konfiguration und Bereitstellung von Services zu automatisieren. Das Kernkonzept ist die Verwendung einer zentralen `service.yml`-Datei als "Single Source of Truth" (SSoT) für jeden Service.

Aus dieser SSoT-Datei generiert eine CI/CD-Pipeline automatisch alle benötigten Konfigurationsmanifeste (z. B. für Docker Compose oder Kubernetes) und orchestriert den gesamten Lebenszyklus eines Services: von der Generierung über die Validierung und das Testen bis hin zur Produktion.

**Hauptmerkmale:**

*   **SSoT-Ansatz:** Eine einzige YAML-Datei definiert alles – von Metadaten des Services über Ports und Volumes bis hin zu umgebungsspezifischen Deployment-Konfigurationen.
*   **Automatisierte Generierung:** Schluss mit manuell gepflegten `docker-compose.yml`- oder Kubernetes-Manifesten. Die Engine generiert sie basierend auf Templates.
*   **GitOps-Workflow:** Änderungen an der `service.yml` lösen einen automatisierten Prozess aus, der die Konfiguration in einem zentralen Infrastruktur-Repository (IAC-Controller) aktualisiert und das Deployment anstößt.
*   **Multi-Stage-Umgebungen:** Ein klar definierter Prozess zur Beförderung (Promotion) von Services durch `dev`-, `test`- und `prod`-Umgebungen.
*   **Automatisierte Dokumentation:** Service-spezifische `documentation.md`-Dateien werden automatisch in einem zentralen Wissensmanagementsystem veröffentlicht.

---

## 2. Systemvoraussetzungen

Damit das Ökosystem aus Template Engine und Deployment-Automatisierung korrekt funktioniert, gibt es eine grundlegende Abhängigkeit zu einer zentralen Ansible-Rolle, die sich im `iac-ansible-automation`-Repository befindet.

**Abhängigkeit: `docker role`**

Diese Ansible-Rolle ist dafür verantwortlich, die Ziel-Systeme (Docker-Hosts) vorzubereiten und sicherzustellen, dass alle für die Services notwendigen externen Ressourcen vorhanden sind. Ihre Hauptaufgaben umfassen:

*   **Docker-Netzwerke:** Erstellung der globalen Docker-Netzwerke (z.B. `services-secured`, `services-exposed`), mit denen sich die Container verbinden.
*   **Basis-Verzeichnisse:** Anlegen der übergeordneten Verzeichnisstrukturen (z.B. `/export/docker`), in denen die persistenten Volume-Daten der Services abgelegt werden.
*   **Berechtigungen:** Setzen der korrekten Datei- und Verzeichnisberechtigungen, um einen reibungslosen Betrieb zu gewährleisten.
*   **SMB-Shares:** Konfiguration von SMB-Freigaben für die Service-Datenverzeichnisse, um einen einfachen und zentralisierten Zugriff auf die persistenten Daten zu ermöglichen.

Ohne die erfolgreiche Ausführung dieser Ansible-Rolle können die von der Template Engine generierten Deployments fehlschlagen, da erwartete Netzwerke oder Verzeichnispfade nicht existieren.

---

## 3. Die `service.yml` Datei

Die `service.yml` ist das Herzstück jedes Services. Sie ist in mehrere logische Abschnitte unterteilt.

### 3.1 `service`

Allgemeine, deployment-unabhängige Informationen über den Service.

| Schlüssel | Typ | Beschreibung | Beispiel |
| :--- | :--- | :--- | :--- |
| `name` | String | Eindeutiger Name des Services. | `aac-traefik` |
| `image_repo` | String | Name des Docker-Images ohne Tag. | `traefik` |
| `image_tag` | String | Tag des Docker-Images. | `latest` |
| `description`| String | Kurze Beschreibung des Services. | `A modern reverse proxy.` |
| `icon` | String | URL zu einem Icon für den Service. | `https://.../traefik.png` |
| `category` | String | Kategorie zur Gruppierung (z.B. im Dashboard). | `Reverse-Proxys` |
| `stage` | String | Standard-Deployment-Stage. | `prod` |
| `hostname` | String | Gewünschter Hostname für den Service. | `traefik` |

### 3.2 `ports`

Eine Liste von Netzwerkports, die der Container bereitstellt.

| Schlüssel | Typ | Beschreibung | Beispiel |
| :--- | :--- | :--- | :--- |
| `name` | String | Logischer Name für den Port. | `websecure` |
| `port` | Integer | Der interne Port des Containers. | `443` |
| `external_port`| Integer | **Optional.** Der Port, der auf dem Host gemappt wird. | `28080` |
| `protocol` | String | Das Protokoll des Ports. | `TCP` |

### 3.3 `volumes`

Eine Liste von Volumes, die der Service benötigt. Die Engine erstellt automatisch benannte Docker-Volumes, die auf dem Host-System als Verzeichnisse gemappt werden.

| Schlüssel | Typ | Beschreibung | Beispiel |
| :--- | :--- | :--- | :--- |
| `name` | String | Logischer Name für das Volume. | `data` |
| `path` | String | Der Pfad, an den das Volume im Container gemountet wird. | `/data` |
| `description`| String | Kurze Beschreibung des Zwecks. | `Für Let's Encrypt Zertifikate` |

#### Physischer Speicherort auf dem Host

Der tatsächliche Pfad auf dem Host-System wird von der Template-Engine standardmäßig nach folgendem Schema aufgebaut:

`<host_base_path>/<service_name>/<volume_name>/
`

*   **`host_base_path`**: Wird aus `deployments.docker_compose.host_base_path` in der `service.yml` bezogen (z.B. `/export/docker`).
*   **`service_name`**: Der Name des Services (z.B. `aac-traefik`).
*   **`volume_name`**: Der logische Name des Volumes aus der Liste (z.B. `data`).

Ein Volume mit dem Namen `data` für den Service `aac-traefik` würde also physisch unter `/export/docker/aac-traefik/data/` auf dem Host-System liegen. Die Erstellung dieses Basis-Pfades und die Vergabe der korrekten Berechtigungen wird durch die `docker role` aus dem `iac-ansible-automation`-Projekt sichergestellt (siehe Abschnitt 2. Systemvoraussetzungen).

### 3.4 `config`

Ein flexibler Abschnitt für anwendungsspezifische Konfigurationen, die in Templates verwendet werden können.

| Schlüssel | Typ | Beschreibung | Beispiel |
| :--- | :--- | :--- | :--- |
| `domain_name`| String | Basis-Domain für das Routing. | `int.fam-feser.de` |
| `cert_resolver`| String | Name des Cert-Resolvers (z.B. für Traefik). | `ionos` |
| `integrations`| Object | Definiert, wie der Service mit anderen Tools im Ökosystem interagiert. Die hier gesetzten Flags und Konfigurationen werden von den Templates genutzt, um z.B. automatisch Service-Widgets für Dashboards oder DNS-Einträge zu erstellen. | `{ "homepage": { "enabled": true }, "autodns": { "enabled": true } }` |

#### Der `integrations`-Block

Dieser Block ist entscheidend für die nahtlose Einbettung eines Services in die bestehende Infrastruktur. Anstatt Konfigurationen in verschiedenen anderen Repositories manuell zu pflegen, deklariert der Service hier seine Teilhabe an bestimmten Systemen.

**Beispiele:**

*   **`homepage`:** Wenn `enabled: true` gesetzt ist, können Templates automatisch die notwendigen Docker-Labels generieren, damit der Service auf einem [Homepage-Dashboard](https.gethomepage.dev/) erscheint.
*   **`autodns`:** Bei `enabled: true` kann ein Prozess angestoßen werden, der automatisch die notwendigen DNS-Einträge für den Service erstellt, basierend auf dem `hostname` und der `domain_name`.

Dieser Abschnitt ist erweiterbar und der Ort, um zukünftige Automatisierungen zu verankern.

### 3.5 `deployments`

Enthält die Konfigurationen für verschiedene Deployment-Ziele.

#### `docker_compose`

| Schlüssel | Typ | Beschreibung | Beispiel |
| :--- | :--- | :--- | :--- |
| `command` | Array | Überschreibt den Standard-Befehl des Containers. | `["my-command", "--flag"]` |
| `restart_policy`| String | Neustart-Richtlinie für den Container. | `always` |
| `host_base_path`| String | Basis-Pfad auf dem Host für Volume-Daten. | `/export/docker` |
| `networks_to_join`| Array | Liste von logischen Netzwerknamen, mit denen der Service verbunden wird. | `[ "secured", "exposed" ]` |
| `network_definitions`| Object | Definition der unter `networks_to_join` verwendeten Netzwerke. | `secured: { name: "services-secured", external: true }` |
| `raw_volumes` | Array | Für direkte Host-Pfad-Mounts (z.B. Docker-Socket). | `[ "/var/run/docker.sock:/var/run/docker.sock" ]` |
| `security_opts` | Array | Setzt Docker Security-Optionen für den Container. | `["no-new-privileges:true"]` |
| `logging` | Object | Konfiguration für das Docker-Logging-Subsystem. | `{ driver: "json-file", options: { "max-size": "10m" } }` |
| `dot_env` | Object | Key-Value-Paare, die als **nicht-geheime** Umgebungsvariablen in die `.env`-Datei geschrieben werden. | `TZ: "Europe/Berlin"` |
| `stack_env` | Object | Key-Value-Paare, die als **geheime** Umgebungsvariablen in die `stack.env`-Datei geschrieben werden. | `IONOS_API_KEY: "secret-key"` |


#### `kubernetes` (Beispiel)

Die Engine unterstützt auch die Generierung von Kubernetes-Manifesten. Der `kubernetes`-Block ist ähnlich strukturiert und dient als SSoT für Kubernetes-Deployments. *(Hinweis: Die Template-Implementierung für Kubernetes ist möglicherweise nicht so vollständig wie für Docker Compose.)*

| Schlüssel | Typ | Beschreibung |
| :--- | :--- | :--- |
| `namespace` | String | Der Kubernetes-Namespace, in dem der Service bereitgestellt wird. |
| `replicas` | Integer | Die Anzahl der Pod-Replicas. |
| `service_type` | String | Der Typ des Kubernetes-Services (z.B. `LoadBalancer`, `NodePort`). |
| `ingress` | Object | Konfiguration für den Ingress-Controller. |
| `persistent_volume_claims`| Object | Definiert die Persistent Volume Claims (PVCs) für stateful Daten. |
| `resources` | Object | Definiert CPU- und Memory-Requests und -Limits für die Pods. |

### 3.6 `dependencies`

Definiert abhängige Services (z.B. Datenbanken, Redis), die zusammen mit dem Hauptservice bereitgestellt werden. Jeder Eintrag in `dependencies` ist im Grunde eine kompakte Service-Definition und kann die meisten der gleichen Schlüssel wie ein Top-Level-Service enthalten, z.B. `image_repo`, `volumes`, `command` und `environment`.

```yaml
dependencies:
  database: # Logischer Name der Abhängigkeit
    name: "firefly-db"
    image_repo: "mariadb"
    image_tag: "latest"
    restart_policy: "unless-stopped"
    networks_to_join:
      - "firefly_internal"
    volumes:
      - name: "db_data"
        path: "/var/lib/mysql"
    environment: # Umgebungsvariablen für den Dependency-Container
      MARIADB_DATABASE: "firefly"
      MARIADB_USER: "firefly"
      MARIADB_PASSWORD: "super-secret-password" # Wird automatisch als Secret behandelt
```

---

## 4. Umgang mit Umgebungsvariablen

Die Engine unterscheidet zwischen zwei Arten von Umgebungsvariablen für den Docker Compose-Generator:

1.  **`.env` (Nicht-geheim):**
    *   Wird aus dem `deployments.docker_compose.dot_env`-Abschnitt der `service.yml` generiert.
    *   Enthält allgemeine Konfigurationen wie Zeitzone, PUID/PGID oder Feature-Flags.
    *   Diese Datei kann sicher in Git eingecheckt werden.

2.  **`stack.env` (Geheim):**
    *   Wird aus dem `deployments.docker_compose.stack_env`-Abschnitt generiert.
    *   Zusätzlich werden `environment`-Variablen aus dem `dependencies`-Block automatisch hierher verschoben, wenn ihr Schlüssel `password`, `secret`, `token` enthält oder der Wert wie ein Geheimnis aussieht.
    *   **Diese Datei ist für Geheimnisse vorgesehen und sollte niemals in Git eingecheckt werden.** Die CI/CD-Pipeline stellt sicher, dass sie sicher an den Deployment-Runner übergeben wird.

---

## 5. Custom Templates

Wenn die Standard-Templates nicht ausreichen, bietet die Engine mächtige Möglichkeiten zur Anpassung und zum Überschreiben von Standardverhalten.

### 5.1 Eigene Konfigurationsdateien

Für anwendungsspezifische Konfigurationsdateien, die mit Jinja2-Loglogik befüllt werden müssen.

*   **Speicherort:** Erstelle ein Verzeichnis `custom_templates/files/` im Root deines Service-Projekts.
*   **Struktur:** Die Verzeichnisstruktur innerhalb von `custom_templates/files/` wird bei der Generierung beibehalten. Eine Datei unter `custom_templates/files/config/my-config.conf.j2` wird zu `deployments/docker_compose/config/my-config.conf` generiert.
*   **Templating:** Du kannst die volle Leistung von Jinja2 nutzen und auf alle Daten aus der `service.yml` zugreifen (z.B. `{{ service.name }}`, `{{ config.domain_name }}`).

Der CI/CD-Job `generate-custom-files` verarbeitet diese Templates automatisch.

### 5.2 Überschreiben von Deployment-Templates

Es ist sogar möglich, die Kern-Deployment-Templates der Engine zu überschreiben. Dies ist nützlich für Services, die eine komplett andere `docker-compose.yml`-Struktur benötigen.

*   **Speicherort:** Lege eine Datei mit dem gleichen Namen wie das Original-Template im Verzeichnis `custom_templates/` ab.
*   **Beispiel:** Um das Standard-Compose-File zu ersetzen, erstelle eine Datei `custom_templates/docker_compose/docker-compose.yml.j2`.
*   **Funktionsweise:** Die CI/CD-Pipeline prüft zuerst, ob ein Custom-Template im Service-Repository existiert. Wenn ja, wird dieses anstelle des Standard-Templates aus der Template-Engine verwendet.

**Achtung:** Das Überschreiben von Kern-Templates sollte mit Vorsicht verwendet werden, da man damit von den Standardisierungen und zukünftigen Updates der zentralen Template-Engine abweicht.

---

## 6. Der GitOps-Automatisierungs-Workflow

Das Herzstück der Automatisierung ist ein ausgeklügelter GitOps-Workflow, der über mehrere Repositories hinweg agiert. Jedes Repository hat eine klar definierte Rolle. Das Zusammenspiel wird durch die zentrale CI/CD-Pipeline aus der Template Engine orcherstriert.

### 6.1 Die Komponenten des Systems

1.  **Applikations-Repository** (z.B. `aac-traefik`, `aac-firefly-iii`)
    *   **Zweck:** Definiert einen einzelnen Service.
    *   **Inhalt:** Enthält die `service.yml` als "Single Source of Truth" für diesen Service, sowie optionale `documentation.md` und `custom_templates`.
    *   **Rolle im Workflow:** Der Startpunkt. Eine Änderung hier (Commit) löst den gesamten Prozess aus.

2.  **`aac-template-engine` (Dieses Repository)**
    *   **Zweck:** Stellt die Logik und die standardisierten Bausteine bereit.
    *   **Inhalt:** Beinhaltet die Jinja2-Templates zur Generierung der Manifeste und vor allem die zentrale, wiederverwendbare CI/CD-Pipeline (`service-pipeline.yml`).
    *   **Rolle im Workflow:** Liefert die Intelligenz und den standardisierten Prozess (die "Blaupause") für die CI/CD-Läufe in den Applikations-Repositories.

3.  **`iac-controller`**
    *   **Zweck:** Das zentrale "State"- oder "Inventory"-Repository. Es repräsentiert den gewünschten Soll-Zustand der gesamten Infrastruktur.
    *   **Inhalt:** Enthält die *generierten* Konfigurationsdateien (`docker-compose.yml`, `.env`, `stack.env` etc.) für *alle* Services in *allen* Umgebungen (`dev`, `test`, `prod`), abgelegt in einer sauberen Verzeichnisstruktur.
    *   **Rolle im Workflow:** Dient als alleinige Quelle für die Deployment-Skripte. Es entkoppelt die Service-Definition von der Ausführung.

4.  **`iac-ansible-automation`**
    *   **Zweck:** Das "Action"-Repository. Es führt die eigentlichen Deployments durch.
    *   **Inhalt:** Enthält die Ansible-Playbooks und -Rollen (wie die `docker role`), die den Soll-Zustand aus dem `iac-controller` lesen und auf den Zielsystemen umsetzen.
    *   **Rolle im Workflow:** Der ausführende Arm. Holt sich den Soll-Zustand und wendet ihn auf den Servern an.

### 6.2 Der Workflow im Detail

Der Prozess wird durch einen einfachen `git push` im Applikations-Repository angestoßen:

1.  **Entwickler-Commit:** Ein Entwickler ändert die `service.yml` (z.B. ein neues Port-Mapping) und pusht die Änderung in den `dev`-Branch des Applikations-Repos.

2.  **CI-Pipeline im App-Repo (Ausgelöst durch den Commit):**
    *   Die eingebundene `service-pipeline.yml` aus der Template Engine startet.
    *   **Generate & Validate:** Die Pipeline generiert die `docker-compose.yml` und alle weiteren Artefakte aus der `service.yml`. Anschließend wird die Konfiguration validiert (z.B. `docker-compose config`).
    *   **Promote (Commit zum `iac-controller`):** Das `promote_service.py`-Skript klont das `iac-controller`-Repository. Es platziert die frisch generierten Dateien in die passende Verzeichnisstruktur (z.B. `inventory/dev/services/aac-firefly-iii/`) und committet diese Änderung mit einer aussagekräftigen Nachricht (z.B. "ci: Promote aac-firefly-iii to dev").

3.  **CI-Pipeline im `iac-controller` (Ausgelöst durch den neuen Commit):**
    *   Der Push vom vorherigen Schritt löst nun eine Pipeline im `iac-controller` aus.
    *   Diese Pipeline hat eine Hauptaufgabe: Sie triggert die Deployment-Pipeline im `iac-ansible-automation`-Repository und übergibt dabei wichtige Informationen, wie z.B. den Namen des geänderten Services.

4.  **CI-Pipeline im `iac-ansible-automation` (Deployment):**
    *   Die ausgelöste Pipeline führt die Ansible-Playbooks aus.
    *   Das Playbook klont seinerseits das `iac-controller`-Repository, um den finalen Soll-Zustand zu lesen.
    *   Ansible verbindet sich mit den Ziel-Hosts und wendet die Konfiguration an (z.B. via `docker-compose up -d`).

### 6.3 Deployment-Szenarien

Dieser Aufbau ermöglicht verschiedene, mächtige Deployment-Strategien:

*   **Single-Service-Deployment (Standardfall):** Wie oben beschrieben. Ein Commit in einem App-Repo führt zum Rollout von nur diesem einen Service. Die Ansible-Pipeline wird dabei mit einem `--limit` auf den betroffenen Service beschränkt, um die Ausführung zu beschleunigen und Seiteneffekte zu vermeiden. Dies wird durch die Variable `DEPLOYMENT_TYPE: 'single_service_trigger'` in der CI/CD gesteuert.

*   **Vollständiges Umgebungs-Deployment:** Manuelle Änderungen oder ein getriggerter Lauf im `iac-controller` können die Ansible-Pipeline ohne `--limit` starten. In diesem Fall würde Ansible den Zustand *aller* im `iac-controller` definierten Services auf *allen* Hosts der jeweiligen Umgebung (z.B. `prod`) überprüfen und ggf. korrigieren. Dies ist nützlich, um Konfigurationsdrift zu beheben oder globale Änderungen auszurollen.

*   **Promotion (`dev` -> `test` -> `prod`):** Die CI/CD-Pipeline im App-Repo enthält manuelle Jobs (`test-promote`, `prod-promote`). Diese erstellen zuerst den entsprechenden Git-Branch (`test` oder `main`) im App-Repository selbst und pushen diesen. Anschließend wiederholen sie den Promote-Prozess für die nächsthöhere Umgebung, indem sie die generierten Artefakte in den entsprechenden `test`- oder `prod`-Pfad im `iac-controller` committen.

---

## 7. Einen neuen Service hinzufügen

1.  **GitLab-Projekt erstellen:** Erstelle ein neues, leeres Projekt in GitLab für deinen Service.
2.  **`service.yml` erstellen:** Lege im Root des Projekts eine `service.yml`-Datei an und fülle sie gemäß der oben beschriebenen Struktur.
3.  **CI/CD-Pipeline einbinden:** Erstelle eine `.gitlab-ci.yml`-Datei mit folgendem Inhalt, um die zentrale Pipeline zu nutzen:
    ```yaml
    include:
      - project: 'aac-application-definitions/aac-template-engine'
        ref: main # Oder eine spezifische Version/Tag
        file: '/templates/cicd/service-pipeline.yml'
    ```
4.  **(Optional) `documentation.md` hinzufügen:** Erstelle eine `documentation.md`-Datei, um deinen Service zu beschreiben.
5.  **(Optional) Custom Templates hinzufügen:** Falls nötig, erstelle das Verzeichnis `custom_templates/files/` und füge deine Jinja2-Templates hinzu.
6.  **Push & Go:** Pushe deine Änderungen in den `dev`-Branch. Die Pipeline startet automatisch, generiert die Konfigurationen und deployt den Service in der Entwicklungsumgebung.

---

## 8. Automatisierte Service-Dokumentation

Ein weiteres Kernmerkmal des Systems ist die Fähigkeit, die technische Dokumentation eines Services direkt aus dessen Repository zu ziehen und zentral zu veröffentlichen.

**Voraussetzung:** Im Root des Applikations-Repositories existiert eine `documentation.md`-Datei.

**Der `publish_to_docs`-Workflow:**

Dieser Prozess wird durch einen manuellen `publish_to_docs`-Job in der CI/CD-Pipeline auf dem `main`-Branch gesteuert:

1.  **Prüfung:** Der Job prüft, ob eine `documentation.md` im Repository vorhanden ist.
2.  **Klonen des Doku-Repos:** Das zentrale Dokumentations-Repository (`documentation/aac-iac-documentation`) wird geklont.
3.  **Hugo-Header-Generierung:** Der Job erstellt dynamisch einen Hugo-kompatiblen "Front Matter"-Header. Dieser enthält Metadaten wie `title`, `date`, `lastmod`, `draft` und `description`.
4.  **Zusammenführung:** Der generierte Header wird mit dem Inhalt der `documentation.md` aus dem App-Repo zusammengefügt.
5.  **Commit & Push:** Die fertige Markdown-Datei wird im Dokumentations-Repository unter `site/content/aac-services/<service-name>/<service-name>-documentation.md` gespeichert, committet und in den `main`-Branch gepusht.

Durch diesen Prozess wird sichergestellt, dass die Dokumentation immer auf dem gleichen Stand wie der Code ist ("Docs as Code") und ohne manuelles Eingreifen in einem zentralen Portal (das mit Hugo gebaut wird) zur Verfügung steht.

---

## 9. Beispiel: Multi-Container Service (Firefly III)

Hier ist ein anonymisiertes Beispiel einer `service.yml` für Firefly III. Es zeigt, wie ein komplexerer Service, der aus mehreren Containern (Hauptanwendung, Datenbank, Redis, Importer, Cron) besteht, definiert wird.

**Wichtige Merkmale dieses Beispiels:**

*   **Mehrere Abhängigkeiten:** `database` (MariaDB), `redis`, `importer` und `cron` sind als Abhängigkeiten definiert.
*   **Inter-Container-Kommunikation:** Die Services nutzen ein internes Docker-Netzwerk (`firefly_internal`), um miteinander zu kommunizieren. Der Hostname für die Datenbank (`{{ dependencies.database.name }}`) wird per Template direkt in die Umgebungsvariablen des Haupt-Services injiziert.
*   **Geheimnis-Management:** Passwörter und App-Keys sind im `stack_env`-Block (oder im `environment`-Block der Abhängigkeiten) platziert, um als Geheimnisse behandelt zu werden.
*   **Komplexe Befehle:** Der `cron`-Container verwendet einen Shell-Befehl, um einen Cron-Job einzurichten.

```yaml
# service.yml für Firefly III (anonymisiert)
service:
  name: "aac-firefly-iii"
  image_repo: "fireflyiii/core"
  image_tag: "latest"
  description: "A free and open source personal finance manager."
  icon: "firefly-iii.png"
  category: "Finanzen"
  stage: "prod"
  hostname: "finance"

ports:
  - name: web
    port: 8080
    external_port: 8765
    protocol: TCP
  - name: importer
    port: 8080
    external_port: 8766
    protocol: TCP

volumes:
  - name: configs
    path: "/var/www/html/storage/upload"
    description: "Configuration and upload storage for Firefly III"

config:
  domain_name: "your-domain.com"
  routing_enabled: true
  cert_resolver: "my-resolver"
  entrypoint: "websecure"
  integrations:
    homepage:
      enabled: true
    autodns:
      enabled: true

deployments:
  docker_compose:
    restart_policy: "always"
    host_base_path: "/export/docker"
    networks_to_join:
      - "secured"
      - "firefly_internal"
      - "docker-default"
    network_definitions:
      secured:
        name: "services-secured"
        external: true
      docker-default:
        name: "docker-default"
        external: true
      firefly_internal:
        name: "firefly_internal"
        driver: "bridge"
    dot_env:
      PUID: "1000"
      PGID: "1000"
      TZ: "Europe/Berlin"
      APP_ENV: "local"
      APP_DEBUG: "false"
      SITE_OWNER: "admin@your-domain.com"
      DEFAULT_LANGUAGE: "de_DE"
      TRUSTED_PROXIES: "**"
      LOG_CHANNEL: "stack"
      APP_LOG_LEVEL: "notice"
      DB_CONNECTION: "mysql"
      DB_HOST: "{{ dependencies.database.name }}"
      DB_PORT: "3306"
      DB_DATABASE: "firefly"
      DB_USERNAME: "firefly"
      REDIS_HOST: "{{ dependencies.redis.name }}"
      REDIS_PORT: "6379"
      MAIL_MAILER: "smtp"
      MAIL_HOST: "smtp.your-provider.com"
      MAIL_PORT: "587"
      MAIL_FROM: "finance@your-domain.com"
      MAIL_USERNAME: "finance@your-domain.com"
      MAIL_ENCRYPTION: "tls"
      APP_URL: "https://{{ service.hostname }}.{{ config.domain_name }}"
    stack_env:
      APP_KEY: "<YOUR_APP_KEY>"
      DB_PASSWORD: "<YOUR_DB_PASSWORD>"
      MAIL_PASSWORD: "<YOUR_MAIL_PASSWORD>"
      STATIC_CRON_TOKEN: "<YOUR_CRON_TOKEN>"

dependencies:
  database:
    name: "firefly-db"
    image_repo: "mariadb"
    image_tag: "latest"
    restart_policy: "unless-stopped"
    networks_to_join:
      - "firefly_internal"
      - "docker-default"
    volumes:
      - name: "db_data"
        path: "/var/lib/mysql"
    environment:
      MARIADB_DATABASE: "firefly"
      MARIADB_USER: "firefly"
      MARIADB_PASSWORD: "<YOUR_DB_PASSWORD>"
      MARIADB_ROOT_PASSWORD: "<A_SECURE_ROOT_PASSWORD>"
  redis:
    name: "firefly-redis"
    image_repo: "redis"
    image_tag: "latest"
    restart_policy: "unless-stopped"
    networks_to_join:
      - "firefly_internal"
    command: ["redis-server", "--appendonly", "yes"]
    volumes:
      - name: "redis_data"
        path: "/data"
  importer:
    name: "firefly-importer"
    image_repo: "fireflyiii/data-importer"
    image_tag: "latest"
    restart_policy: "always"
    networks_to_join:
      - "secured"
      - "firefly_internal"
      - "docker-default"
    volumes:
      - name: "importer_upload"
        path: "/var/www/html/storage/upload"
    environment:
      FIREFLY_III_URL: "http://{{ service.name | lower }}:8080"
      VANITY_URL: "https://{{ service.hostname }}.{{ config.domain_name }}"
      TZ: "Europe/Berlin"
      TRUSTED_PROXIES: "**"
      APP_DEBUG: "false"
      LOG_LEVEL: "debug"
      VERIFY_TLS_SECURITY: "false"
      FIREFLY_III_CLIENT_ID: "1"
      REDIS_HOST: "{{ dependencies.redis.name }}"
      REDIS_PORT: "6379"
  cron:
    name: "firefly-cron"
    image_repo: "alpine"
    image_tag: "latest"
    restart_policy: "always"
    networks_to_join:
      - "secured"
      - "docker-default"
    command:
      - "sh"
      - "-c"
      - "echo \"0 3 * * * wget -qO- https://{{ service.hostname }}.{{ config.domain_name }}/api/v1/cron/{{ deployments.docker_compose.stack_env.STATIC_CRON_TOKEN }}\" | crontab - && crond -f -L /dev/stdout"
```
