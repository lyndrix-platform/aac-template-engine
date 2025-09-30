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

## 2. Die `service.yml` Datei

Die `service.yml` ist das Herzstück jedes Services. Sie ist in mehrere logische Abschnitte unterteilt.

### 2.1 `service`

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

### 2.2 `ports`

Eine Liste von Netzwerkports, die der Container bereitstellt.

| Schlüssel | Typ | Beschreibung | Beispiel |
| :--- | :--- | :--- | :--- |
| `name` | String | Logischer Name für den Port. | `websecure` |
| `port` | Integer | Der interne Port des Containers. | `443` |
| `external_port`| Integer | **Optional.** Der Port, der auf dem Host gemappt wird. | `28080` |
| `protocol` | String | Das Protokoll des Ports. | `TCP` |

### 2.3 `volumes`

Eine Liste von Volumes, die der Service benötigt. Die Engine erstellt automatisch benannte Docker-Volumes.

| Schlüssel | Typ | Beschreibung | Beispiel |
| :--- | :--- | :--- | :--- |
| `name` | String | Logischer Name für das Volume. | `data` |
| `path` | String | Der Pfad, an den das Volume im Container gemountet wird. | `/data` |
| `description`| String | Kurze Beschreibung des Zwecks. | `Für Let's Encrypt Zertifikate` |

### 2.4 `config`

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

### 2.5 `deployments`

Enthält die Konfigurationen für verschiedene Deployment-Ziele.

#### `docker_compose`

| Schlüssel | Typ | Beschreibung | Beispiel |
| :--- | :--- | :--- | :--- |
| `restart_policy`| String | Neustart-Richtlinie für den Container. | `always` |
| `host_base_path`| String | Basis-Pfad auf dem Host für Volume-Daten. | `/export/docker` |
| `networks_to_join`| Array | Liste von logischen Netzwerknamen, mit denen der Service verbunden wird. | `[ "secured", "exposed" ]` |
| `network_definitions`| Object | Definition der unter `networks_to_join` verwendeten Netzwerke. | `secured: { name: "services-secured", external: true }` |
| `raw_volumes` | Array | Für direkte Host-Pfad-Mounts (z.B. Docker-Socket). | `[ "/var/run/docker.sock:/var/run/docker.sock" ]` |
| `dot_env` | Object | Key-Value-Paare, die als **nicht-geheime** Umgebungsvariablen in die `.env`-Datei geschrieben werden. | `TZ: "Europe/Berlin"` |
| `stack_env` | Object | Key-Value-Paare, die als **geheime** Umgebungsvariablen in die `stack.env`-Datei geschrieben werden. | `IONOS_API_KEY: "secret-key"` |

### 2.6 `dependencies`

Definiert abhängige Services (z.B. Datenbanken, Redis), die zusammen mit dem Hauptservice bereitgestellt werden. Jeder Eintrag in `dependencies` ist im Grunde eine kompakte Service-Definition.

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

## 3. Umgang mit Umgebungsvariablen

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

## 4. Custom Templates

Wenn die Standard-Templates nicht ausreichen, bietet die Engine mächtige Möglichkeiten zur Anpassung und zum Überschreiben von Standardverhalten.

### 4.1 Eigene Konfigurationsdateien

Für anwendungsspezifische Konfigurationsdateien, die mit Jinja2-Logik befüllt werden müssen.

*   **Speicherort:** Erstelle ein Verzeichnis `custom_templates/files/` im Root deines Service-Projekts.
*   **Struktur:** Die Verzeichnisstruktur innerhalb von `custom_templates/files/` wird bei der Generierung beibehalten. Eine Datei unter `custom_templates/files/config/my-config.conf.j2` wird zu `deployments/docker_compose/config/my-config.conf` generiert.
*   **Templating:** Du kannst die volle Leistung von Jinja2 nutzen und auf alle Daten aus der `service.yml` zugreifen (z.B. `{{ service.name }}`, `{{ config.domain_name }}`).

Der CI/CD-Job `generate-custom-files` verarbeitet diese Templates automatisch.

### 4.2 Überschreiben von Deployment-Templates

Es ist sogar möglich, die Kern-Deployment-Templates der Engine zu überschreiben. Dies ist nützlich für Services, die eine komplett andere `docker-compose.yml`-Struktur benötigen.

*   **Speicherort:** Lege eine Datei mit dem gleichen Namen wie das Original-Template im Verzeichnis `custom_templates/` ab.
*   **Beispiel:** Um das Standard-Compose-File zu ersetzen, erstelle eine Datei `custom_templates/docker_compose/docker-compose.yml.j2`.
*   **Funktionsweise:** Die CI/CD-Pipeline prüft zuerst, ob ein Custom-Template im Service-Repository existiert. Wenn ja, wird dieses anstelle des Standard-Templates aus der Template-Engine verwendet.

**Achtung:** Das Überschreiben von Kern-Templates sollte mit Vorsicht verwendet werden, da man damit von den Standardisierungen und zukünftigen Updates der zentralen Template-Engine abweicht.

---

## 5. Der CI/CD-GitOps-Workflow

Die `service-pipeline.yml` definiert einen mehrstufigen GitOps-Prozess:

1.  **`generate`:** (Auf `dev`-Branch)
    *   Die `generate_manifest.py`-Skripte werden ausgeführt.
    *   `docker-compose.yml`, `.env`, `stack.env` und Custom Files werden aus der `service.yml` generiert und als Artefakte gespeichert.

2.  **`validate`:** (Auf `dev`-Branch)
    *   Die Syntax der generierten `docker-compose.yml` wird mit `docker-compose config` überprüft.

3.  **`dev-promote-and-deploy`:** (Auf `dev`-Branch)
    *   Das `promote_service.py`-Skript wird ausgeführt.
    *   Es klont das zentrale `iac-controller`-Repository.
    *   Die Konfiguration des Services für die `dev`-Umgebung wird dort hinzugefügt oder aktualisiert.
    *   Ein Commit wird in das `iac-controller`-Repo gepusht, was wiederum die zentrale Ansible-Deployment-Pipeline für die `dev`-Umgebung auslöst.

4.  **`test-promote` & `test-deploy`:** (Manuell auf `dev`-Branch)
    *   Ein manueller Job, der einen `test`-Branch erstellt und den Service in der `test`-Umgebung im `iac-controller`-Repo registriert.
    *   Löst das Deployment in der Test-Umgebung aus.

5.  **`prod-promote` & `prod-deploy`:** (Auf `test`-Branch)
    *   Befördert die Konfiguration vom `test`- in den `main`-Branch und registriert den Service für die `prod`-Umgebung.
    *   Löst (manuell) das finale Deployment in der Produktionsumgebung aus.

6.  **`publish_to_docs`:** (Manuell auf `main`-Branch)
    *   Wenn eine `documentation.md` im Service-Repository existiert, wird diese automatisch in das zentrale Dokumentationsportal (`aac-iac-documentation`) publiziert.

---

## 6. Einen neuen Service hinzufügen

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
