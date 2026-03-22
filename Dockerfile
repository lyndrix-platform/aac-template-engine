# Start from your monolithic Ansible CI image
FROM registry.gitlab.int.fam-feser.de/iac-environment/iac-platform-assets/ansible-ci-image:latest

# Install ONLY the missing dependencies for the template engine
# (zensical and docker are already provided by the base image)
RUN pip install --no-cache-dir pyyaml jinja2 mkdocs-material

# Copy the engine logic into a fixed, globally accessible directory
COPY scripts/ /opt/aac-template-engine/scripts/

# Explicitly add the scripts directory to the Python path globally
ENV PYTHONPATH="/opt/aac-template-engine/scripts:${PYTHONPATH}"

# Define the standard GitLab CI working directory
WORKDIR /builds