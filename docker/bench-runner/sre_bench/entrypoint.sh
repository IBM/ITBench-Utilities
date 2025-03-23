#!/bin/bash

PATH_TO_CONFIG=$1

kops export kubecfg --admin --name=$AWX_CLUSTERNAME --state=s3://$S3_BUCKET_NAME --kubeconfig /tmp/$AWX_CLUSTERNAME.yaml
cd /etc/agent-benchmark
python itbench_utilities/main.py runner \
    -c $PATH_TO_CONFIG \
    --runner_id runner1 \
    --service_type SRE