#!/bin/bash

cd /etc/agent-benchmark

port="443"
root_path="/bench-server"
benchmark_timeout="300"
benchmark_exec_max_attempts="10"
benchmark_exec_retry_interval="60"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) host="$2"; shift 2 ;;
    --port) port="$2"; shift 2 ;;
    --root_path) root_path="$2"; shift 2 ;;
    --benchmark_timeout) benchmark_timeout="$2"; shift 2 ;;
    --benchmark_exec_max_attempts) benchmark_exec_max_attempts="$2"; shift 2 ;;
    --benchmark_exec_retry_interval) benchmark_exec_retry_interval="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

export PYTHONUNBUFFERED=1

python itbench_utilities/agent_harness/main.py \
  --agent_directory /etc/ciso-agent \
  -i /tmp/agent-manifest.json \
  -c /etc/ciso-agent/agent-harness.yaml \
  --host $host \
  --port $port \
  --root_path $root_path \
  --ssl \
  --benchmark_timeout $benchmark_timeout \
  --benchmark_exec_max_attempts $benchmark_exec_max_attempts \
  --benchmark_exec_retry_interval $benchmark_exec_retry_interval \
  --single_run