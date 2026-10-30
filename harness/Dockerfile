# Agent image for the feature-consolidation experiment.
# Build once before the pilot:   docker build -t mve-agent:frozen harness/
# Record the digest:              docker image inspect --format '{{.Id}}' mve-agent:frozen
# Never rebuild between runs: the image is the pinned runtime (CLI, Python, test and metric tools).
FROM node:22-bookworm-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-pip git make ca-certificates \
 && rm -rf /var/lib/apt/lists/*
RUN pip3 install --no-cache-dir --break-system-packages pytest pytest-timeout lizard==1.24.3 radon ruff==0.17.3
RUN npm install -g @github/copilot@1.0.105 jscpd@5.4.1 && npm cache clean --force
RUN git config --system --add safe.directory /work
WORKDIR /work
