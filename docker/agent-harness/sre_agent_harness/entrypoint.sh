#!/bin/bash

remote_host=$1
remote_port=$2
agent_id=$3
agent_token=$4
agent_directory=$5
benchmark_timeout=$6

endpoint="https://$remote_host"
if [[ $remote_port -gt 0 ]]; then
        endpoint="https://$remote_host:$remote_port"
fi

curl -k -s -X GET -H "Authorization: Bearer $agent_token" "$endpoint/registry/agent-manifest/$agent_id" > /tmp/agent-manifest.json
echo "Agent manifest has been obtained."

python -u itbench_utilities/agent_harness/main.py \
        --host $remote_host \
        --port $remote_port \
        --agent_directory $agent_directory \
        -c $agent_directory/agent-harness-sre.yaml \
        -i /tmp/agent-manifest.json \
        --ssl \
        --benchmark_timeout $benchmark_timeout