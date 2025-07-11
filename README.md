# AaC Template Engine

## Description

The AaC Template Engine is a Python-based tool for generating configuration files and other text-based outputs from a central Single Source of Truth (SSoT) file. It utilizes Jinja2 templating to render dynamic content based on data defined in the SSoT file, allowing for consistent and easily maintainable configurations across different environments and deployments.

## Features

*   **SSoT-Driven:** Configurations are generated from a single, central YAML file, reducing redundancy and improving consistency.
*   **Jinja2 Templating:** Leverages the powerful Jinja2 templating engine for dynamic content generation, including variable substitution, loops, conditionals, and filters.
*   **Customizable Templates:** Supports both standard templates and custom templates for different deployment types, allowing for flexible configuration management.
*   **File Processing:** Can process and render individual files, enabling the generation of complete deployment packages or specific configuration sets.
*   **GitLab CI/CD Integration:** Designed for integration with GitLab CI/CD pipelines, automating the generation, validation, and deployment of configurations.

## Installation

1.  **Clone the repository:**

    ```bash
    git clone <repository_url>
    cd aac-template-engine
    ```

2.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

## Usage

The main script is `scripts/generate_manifest.py`. It takes an SSoT file as input and generates outputs based on the specified deployment type or processes custom files.

**Command-line arguments:**

*   `--ssot-file`:  Path to the central SSoT YAML file. (Required)
*   `--deployment-type`: The deployment type to generate (e.g., `docker_compose`, `kubernetes`).  (Mutually exclusive with `--process-files`)
*   `--process-files`: Processes custom files from `custom_templates/files/`. (Mutually exclusive with `--deployment-type`)

**Example:**

To generate Docker Compose configurations:

```bash
python scripts/generate_manifest.py --ssot-file service.yml --deployment-type docker_compose
```

To process custom files:

```bash
python scripts/generate_manifest.py --ssot-file service.yml --process-files
```

**Directory structure:**

*   `service.yml`:  The central SSoT file containing service definitions and deployment configurations.
*   `templates/<deployment_type>/`:  Standard templates for different deployment types.
*   `custom_templates/<deployment_type>/`:  Custom templates that override the standard ones for a specific deployment type.
*   `custom_templates/files/`:  Contains custom files and directories that need to be copied or rendered.  The directory structure within `custom_templates/files/` will be preserved in the output.
*   `deployments/<deployment_type>/`: Output directory for generated deployment manifests.
*   `deployments/files/`: Output directory for processed custom files.

## Contributing

Contributions are welcome! Please follow these steps:

1.  Fork the repository.
2.  Create a new branch for your feature or bug fix:  `git checkout -b feature/my-new-feature` or `git checkout -b fix/my-bug-fix`
3.  Make your changes, ensuring that they are well-tested.
4.  Run the tests (if any) using the GitLab CI/CD pipeline defined in `.gitlab-ci.yml`.
5.  Commit your changes with clear and concise messages.
6.  Push your branch to your fork.
7.  Create a merge request against the `dev` branch of the main repository.

## License

This project is licensed under the [Specify the license here, e.g., MIT License].

## Project Status

[Optional: Add a note about the project's current status, e.g., actively maintained, in development, etc.]