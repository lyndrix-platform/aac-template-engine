# Start from your monolithic Ansible CI image
FROM registry.gitlab.int.fam-feser.de/iac-environment/iac-platform-assets/ansible-ci-image:latest

# Install dependencies (zensical and docker-compose are already in the base)
RUN pip install --no-cache-dir pyyaml jinja2 mkdocs-material

# --- THE FIX: Copy the complete engine environment ---
# We use a single target directory /opt/aac-template-engine
# and copy the essential folders from your tree
COPY scripts/   /opt/aac-template-engine/scripts/
COPY catalog/   /opt/aac-template-engine/catalog/
COPY templates/ /opt/aac-template-engine/templates/

# Set the PYTHONPATH so the manifest_generator module is always findable
ENV PYTHONPATH="/opt/aac-template-engine/scripts:${PYTHONPATH}"

# Default workdir for GitLab CI
WORKDIR /builds