# Start from your monolithic Ansible CI image
FROM registry.gitlab.int.fam-feser.de/iac-environment/iac-platform-assets/ansible-ci-image:latest

# Install Python dependencies for the template engine and MkDocs
RUN pip install --no-cache-dir pyyaml jinja2 mkdocs-material

# CRITICAL: Install Ansible Collections needed for Docker and Swarm
# This prevents the "couldn't resolve module/action" error in CI
RUN ansible-galaxy collection install community.docker

# 1. Pre-create SSH directory and set permissions
RUN mkdir -p /root/.ssh && chmod 700 /root/.ssh



# 2. Set the Ansible Config environment variable globally
# Note: Ensure this path matches where GitLab CI checks out your code
ENV ANSIBLE_CONFIG="/builds/iac-environment/iac-ansible-automation/ansible.cfg"
ENV PYTHONPATH="/opt/aac-template-engine/scripts"


# 3. Copy the complete engine environment
COPY scripts/   /opt/aac-template-engine/scripts/
COPY catalog/   /opt/aac-template-engine/catalog/
COPY templates/ /opt/aac-template-engine/templates/

# 4. Set the PYTHONPATH so the manifest_generator module is always findable
ENV PYTHONPATH="/opt/aac-template-engine/scripts:${PYTHONPATH}"

# Default workdir for GitLab CI
WORKDIR /builds