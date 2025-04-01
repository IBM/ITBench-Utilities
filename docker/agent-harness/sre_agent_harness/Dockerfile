FROM python:3.12-slim

WORKDIR /app

RUN apt update -y && apt install -y curl gnupg2 jq
RUN mkdir /app/agent-benchmark
COPY itbench_utilities /app/agent-benchmark/itbench_utilities
COPY pyproject.toml /app/agent-benchmark/pyproject.toml
RUN pip install --upgrade setuptools
RUN pip install -e /app/agent-benchmark --no-cache-dir
RUN ln -sf /bin/bash /bin/sh

WORKDIR /app/agent-benchmark
