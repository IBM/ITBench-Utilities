#!/bin/bash

cd /etc/agent-benchmark

port="443"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) host="$2"; shift 2 ;;
    --port) port="$2"; shift 2 ;;
    --runner_id) runner_id="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

sed -i "s/^host: .*/host: \"$host\"/" /etc/config.yaml
sed -i "s/^port: .*/port: $port/" /etc/config.yaml

token=`jq -r .token /tmp/agent-manifest.json`

python itbench_utilities/bench_runner/main.py runner \
  -c /etc/config.yaml \
  --runner_id $runner_id \
  --token $token \
  --single_run