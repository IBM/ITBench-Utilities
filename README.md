# IT-Bench Utilities

This repository provides a toolkit for [ITBench](https://github.com/IBM/itbench), including the containerized components used to run and evaluate agents.

## 🎞️ Components

- **bench-runner**: Executes benchmark scenarios.
- **agent-harness**: Wraps agents for interaction with IT Bench Service.

## 🛠️ Build and Push (Multi-Arch)

```bash
bench_runner_name="ghcr.io/ibm/itbench-utilities/bench-runner-base:0.0.1"
agent_harness_name="ghcr.io/ibm/itbench-utilities/agent-harness-base:0.0.1"

# Build and push bench-runner base image
docker buildx build --platform linux/amd64,linux/arm64 \
  -f ./docker/bench-runner/Dockerfile \
  -t ${bench_runner_name} \
  . --push

# Build and push agent-harness base image
docker buildx build --platform linux/amd64,linux/arm64 \
  -f ./docker/agent-harness/Dockerfile \
  -t ${agent_harness_name} \
  . --push
```

## 📝 Notes

- Make sure `docker buildx` is installed and configured with a builder that supports multi-platform builds.
- You need to be logged in to the container registry (`icr.io`) before pushing.
