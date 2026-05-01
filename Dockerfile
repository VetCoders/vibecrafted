FROM node:22-bookworm-slim

ARG INSTALL_AGENT_CLIS=false
ARG INSTALL_FOUNDATIONS=false

ENV DEBIAN_FRONTEND=noninteractive \
    NODE_ENV=production \
    PYTHONUNBUFFERED=1 \
    VIBECRAFTED_ROOT=/workspace \
    VIBECRAFTED_HOME=/workspace/.vibecrafted \
    VIBECRAFTED_SOURCE=/opt/vibecrafted \
    PATH=/opt/vibecrafted/scripts:/workspace/.vibecrafted/bin:/root/.local/bin:/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

WORKDIR /opt/vibecrafted

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    curl \
    git \
    jq \
    make \
    openssh-client \
    python3 \
    python3-venv \
    ripgrep \
    tar \
    unzip \
    xz-utils \
    zsh \
  && curl -LsSf https://astral.sh/uv/install.sh | UV_INSTALL_DIR="/usr/local/bin" sh \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY . /opt/vibecrafted

RUN chmod +x \
    /opt/vibecrafted/install.sh \
    /opt/vibecrafted/scripts/vibecraft \
    /opt/vibecrafted/scripts/vibecrafted \
    /opt/vibecrafted/scripts/install-foundations.sh \
    /opt/vibecrafted/docker/entrypoint.sh \
  && ln -sf /opt/vibecrafted/scripts/vibecrafted /usr/local/bin/vibecrafted \
  && ln -sf /opt/vibecrafted/scripts/vibecraft /usr/local/bin/vibecraft \
  && ln -sf /opt/vibecrafted/docker/entrypoint.sh /usr/local/bin/vibecrafted-docker-entrypoint \
  && (uv sync --project /opt/vibecrafted/scripts/installer --locked || uv sync --project /opt/vibecrafted/scripts/installer)

RUN if [ "$INSTALL_AGENT_CLIS" = "true" ]; then \
    npm install -g \
      @anthropic-ai/claude-code \
      @openai/codex \
      @google/gemini-cli; \
  fi

RUN if [ "$INSTALL_FOUNDATIONS" = "true" ]; then \
    VIBECRAFTED_BIN=/usr/local/bin bash /opt/vibecrafted/scripts/install-foundations.sh --all; \
  fi

RUN mkdir -p /workspace /workspace/.vibecrafted \
  && git config --global --add safe.directory /workspace \
  && vibecrafted version

WORKDIR /workspace

ENTRYPOINT ["vibecrafted-docker-entrypoint"]
CMD ["help"]
