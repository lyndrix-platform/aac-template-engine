
# AAC Template Engine ⚙️

The **AAC (Automation as Code) Template Engine** is a powerful, CI/CD-native tool designed to generate deployment configurations from a single YAML file (`service.yml`). It leverages the Jinja2 templating engine to enforce consistency, reduce boilerplate, and streamline the management of application deployments based on a **Single Source of Truth (SSoT)**.

This engine is built to be integrated directly into a GitLab CI/CD pipeline, automating the entire workflow from configuration change to deployment promotion.

-----

## Core Concepts

  * **Single Source of Truth (`service.yml`)**: All configuration for a service—from its Docker image and port mappings to its environment variables and dependencies—is defined in a single `service.yml` file within the service's repository.

  * **Recursive Templating**: The engine first resolves any Jinja2 expressions *within* the `service.yml` file itself. This allows for creating dynamic and self-referential configurations (e.g., defining a database container name based on the main service name).

  * **Template Override System**: The engine uses a layered approach for templates. It will always look for a service-specific template in the service's `custom_templates/` directory first. If one isn't found, it falls back to the default templates provided by the central template engine repository. This provides both standardization and flexibility.

  * **CI/CD Automation**: The entire process is automated. When a developer pushes a change to `service.yml` on the `dev` branch, the pipeline automatically generates, validates, and commits the resulting deployment manifests. It then promotes these changes through `test` and `main` branches, ensuring a reliable "GitOps" style workflow.

-----

## How It Works: The CI/CD Pipeline

The process is managed by the `service-pipeline.yml` in GitLab CI:

1.  **Change**: A developer modifies the `service.yml` file in their service repository and pushes to the `dev` branch.
2.  **Generate**: The `generate` stage kicks off. It reads `service.yml`, converts it to JSON, and feeds it into the `generate_manifest.py` script. The script renders all necessary deployment files (e.g., `docker-compose.yml`, `.env`, `stack.env`) into the `deployments/` directory.
3.  **Validate**: The `validate` stage checks the syntax and integrity of the generated files (e.g., using `docker-compose config`).
4.  **Commit**: If the generated files have changed, the pipeline automatically commits them back to the `dev` branch with the message `ci: Auto-generate deployment manifests [skip ci]`.
5.  **Promote**: The pipeline then automatically force-pushes the `dev` branch to `test`, and subsequently to `main`, moving the fully-defined deployment state across environments.

-----

## Deep Dive: The `service.yml` for Docker Compose

The `service.yml` is the heart of the system. Its structure is parsed and used to render the Jinja2 templates. Below is a detailed breakdown of the possible keys for a `docker_compose` deployment.

### Example `service.yml`

```yaml
# ----------------------------------------------------------------
# Main service definition
# ----------------------------------------------------------------
service:
  name: "MyApp"
  description: "A description of MyApp for the homepage."
  category: "Services" # Group for the homepage
  icon: "mdi-rocket" # Homepage icon (from Material Design Icons)
  hostname: "myapp-dev" # DNS hostname (e.g., myapp-dev.example.com)
  image_repo: "my-registry/myapp"
  image_tag: "latest"

# ----------------------------------------------------------------
# Port mappings for the main service
# The 'name' field helps identify ports for specific integrations like Traefik.
# Common names: 'web', 'http', 'dashboard'. The first port is the default.
# ----------------------------------------------------------------
ports:
  - name: "web"
    port: 8080
  - name: "metrics"
    port: 9090

# ----------------------------------------------------------------
# Volume mappings for the main service
# The 'name' is the subdirectory created on the host. 'path' is the container path.
# Host path becomes: /data/services/myapp/config -> /etc/myapp
# ----------------------------------------------------------------
volumes:
  - name: "config"
    path: "/etc/myapp"
  - name: "data"
    path: "/var/lib/myapp/data"

# ----------------------------------------------------------------
# Global configuration for integrations
# ----------------------------------------------------------------
config:
  domain_name: "example.com"
  routing_enabled: true # Master switch for creating Traefik labels
  entrypoint: "websecure" # Traefik entrypoint (e.g., web, websecure)
  cert_resolver: "letsencrypt" # Traefik certificate resolver
  integrations:
    autodns:
      enabled: true
      create_wildcard: false
    homepage:
      enabled: true
      # Optional widget configuration for the homepage
      widget:
        type: "my-app"
        url: "https://{{ service.hostname }}.{{ config.domain_name }}"
        key: "{{ deployments.docker_compose.stack_env.MYAPP_API_KEY }}" # Can reference other values

# ----------------------------------------------------------------
# Deployment-specific configurations
# ----------------------------------------------------------------
deployments:
  docker_compose:
    # Base path on the Docker host for all volumes
    host_base_path: "/data/services"
    restart_policy: "unless-stopped"
    
    # List of networks the main service should join
    networks_to_join:
      - "backend"
      - "secured" # Typically the Traefik network
      
    # Environment variables are split into two files:
    # .env: For non-sensitive data, committed to Git.
    # stack.env: For secrets. This file should be in .gitignore and managed by Ansible/Vault.
    dot_env:
      LOG_LEVEL: "info"
      FEATURE_FLAG_X: "true"
      DB_HOST: "{{ dependencies.database.name }}" # Jinja templating is allowed here!
    stack_env:
      # Keywords 'secret', 'password', 'token' automatically place vars here,
      # but they can also be defined explicitly.
      MYAPP_API_KEY: "{{ some_vault_secret }}"
      
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: "60s"
      timeout: "10s"
      retries: 5
      
    # Define the networks to be created by this compose file
    network_definitions:
      backend:
        name: "myapp_backend_net"
        driver: "bridge"
      secured:
        name: "traefik_proxy"
        external: true # Marks this network as pre-existing

# ----------------------------------------------------------------
# Service dependencies (e.g., databases, caches)
# ----------------------------------------------------------------
dependencies:
  database: # Logical name of the dependency
    name: "{{ service.name | lower }}-db" # Actual container name, templated
    image_repo: "postgres"
    image_tag: "15-alpine"
    networks_to_join:
      - "backend"
    volumes:
      - name: "db-data" # Host path: /data/services/myapp/db-data
        path: "/var/lib/postgresql/data"
    # Environment variables for the dependency.
    # The script automatically sorts them into .env or stack.env
    # based on name (e.g., 'password') or value (e.g., '{{ a_secret }}').
    environment:
      POSTGRES_USER: "myapp"
      POSTGRES_DB: "myapp_db"
      POSTGRES_PASSWORD: "{{ vault_postgres_password }}" # Automatically goes to stack.env
```

-----

## Script Usage

The core logic resides in `scripts/generate_manifest.py`. It's designed to be run by the CI pipeline, not manually.

### Arguments

  * `--ssot-json`: **(Required)** The complete SSoT data as a JSON string. The CI pipeline generates this by converting `service.yml`.
  * `--template-path`: **(Required)** The absolute path to the main template engine directory, containing the default templates.
  * `--deployment-type <type>`: Generates manifests for a specific type (e.g., `docker_compose`). It looks for templates in `custom_templates/<type>/` and `templates/<type>/`.
  * `--process-files`: A special mode to process generic files. It looks for templates in `custom_templates/files/` and `templates/files/`.

-----

## Directory Structure

A typical service repository using this engine would look like this:

```
.
├── .gitlab-ci.yml              # CI configuration for the service
├── service.yml                 # THE SINGLE SOURCE OF TRUTH
|
├── custom_templates/           # Optional: Service-specific template overrides
│   ├── docker_compose/
│   │   └── docker-compose.yml.j2 # Overrides the default docker-compose template
│   └── files/
│       └── my_custom_config.txt.j2 # A custom templated file
|
└── deployments/                # AUTO-GENERATED: Do not edit manually!
    ├── docker_compose/
    │   ├── docker-compose.yml
    │   ├── .env
    │   └── stack.env
    └── files/
        └── my_custom_config.txt
```

-----

## Contributing

Contributions to the template engine should follow the standard Git flow:

1.  **Fork** the template engine repository.
2.  Create a new feature branch: `git checkout -b feature/my-new-feature`.
3.  Make your changes and commit them with clear messages.
4.  Push your branch to your fork.
5.  Create a **Merge Request** against the `dev` branch of the main repository.