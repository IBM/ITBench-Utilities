FROM python:3.11-slim

LABEL org.opencontainers.image.source=https://github.com/IBM/ITBench-Utilities

RUN apt update -y && apt install -y curl gnupg2 unzip
RUN mkdir /etc/agent-benchmark
COPY itbench_utilities /etc/agent-benchmark/itbench_utilities
COPY pyproject.toml /etc/agent-benchmark/pyproject.toml
COPY docker/bench-runner/entrypoint.sh /etc/entrypoint.sh
COPY docker/bench-runner/config.yaml /etc/config.yaml
RUN chmod +x /etc/entrypoint.sh
RUN pip install --upgrade setuptools
RUN pip install -e /etc/agent-benchmark --no-cache-dir
RUN ln -sf /bin/bash /bin/sh

WORKDIR /etc/agent-benchmark


ENTRYPOINT ["/etc/entrypoint.sh"]