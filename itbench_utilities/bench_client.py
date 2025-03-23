# Copyright contributors to the ITBench project. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import asyncio
import logging
from typing import Any, Dict, List, Optional

import requests
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from starlette.status import HTTP_404_NOT_FOUND

from itbench_utilities.app.models.agent import Agent
from itbench_utilities.app.models.base import AgentPhaseEnum, BundlePhaseEnum
from itbench_utilities.app.models.benchmark import Benchmark
from itbench_utilities.app.models.bundle import Bundle as BundleInApp
from itbench_utilities.app.models.result import ResultSpec
from itbench_utilities.app.utils import create_status
from itbench_utilities.common.rest_client import RestClient
from itbench_utilities.models.benchmark import BenchRunConfig
from itbench_utilities.models.bundle import Bundle, BundleResult

logger = logging.getLogger(__name__)


class BenchNotFoundException(Exception):
    pass


class BenchClient:

    def __init__(self, bench_run_config: BenchRunConfig, rest_client: Optional[RestClient] = None, user_id: Optional[str] = None) -> None:
        self.bench_run_config = bench_run_config
        self.user_id = user_id
        self.client = rest_client

    def validate_benchmark(self):
        try:
            bench_run_config = self.bench_run_config
            if bench_run_config.push_model:
                endpoint = f"/benchmarks/{self.bench_run_config.benchmark_id}"
                response = self.client.get(endpoint)
                Benchmark.model_validate(response.json())
        except HTTPException as e:
            if e.status_code == HTTP_404_NOT_FOUND:
                raise BenchNotFoundException(f"Benchmark id '{self.bench_run_config.benchmark_id}' is not found.")
        except Exception as e:
            raise e

    def push_bundle_status(self, bundle_id: str, phase: BundlePhaseEnum, message: Optional[str] = None):
        bench_run_config = self.bench_run_config
        if bench_run_config.push_model:
            status = create_status(phase.value, message)
            endpoint = f"/benchmarks/{self.bench_run_config.benchmark_id}/bundles/{bundle_id}/status"
            self.client.put(endpoint, status.model_dump_json())

    def push_bundle_data(self, bundle_id: str, data: Optional[Dict[str, Any]] = None):
        bench_run_config = self.bench_run_config
        if bench_run_config.push_model:
            endpoint = f"/benchmarks/{self.bench_run_config.benchmark_id}/bundles/{bundle_id}"
            res = self.client.get(endpoint)
            bundle = BundleInApp.model_validate(res.json())
            bundle.spec.data = data
            self.client.put(endpoint, bundle.spec.model_dump_json())

    def push_agent_status(self, agent_id: str, phase: AgentPhaseEnum, message: Optional[str] = None):
        bench_run_config = self.bench_run_config
        if bench_run_config.push_model:
            status = create_status(phase.value, message)
            endpoint = f"/benchmarks/{self.bench_run_config.benchmark_id}/agents/{agent_id}/status"
            self.client.put(endpoint, status.model_dump_json())

    def get_agent_status(self, agent_id: str) -> Agent:
        bench_run_config = self.bench_run_config
        if bench_run_config.push_model:
            endpoint = f"/benchmarks/{self.bench_run_config.benchmark_id}/agents/{agent_id}"
            res = self.client.get(endpoint)
            return Agent.model_validate(res.json())

    def upload_bundle_results(self, bundle: Bundle, bundle_results: List[BundleResult]):
        bench_run_config = self.bench_run_config
        if bench_run_config.push_model:
            result_specs: List[ResultSpec] = [
                ResultSpec(
                    bundle_id=bundle.id,
                    name=x.name,
                    description=x.description,
                    incident_type=x.incident_type,
                    agent=x.agent,
                    passed=x.passed,
                    ttr=x.ttr,
                    errored=x.errored,
                    date=x.date,
                    message=x.message,
                )
                for x in bundle_results
            ]
            endpoint = f"/benchmarks/{self.bench_run_config.benchmark_id}/results/bulk"
            to_str = ",".join([x.model_dump_json() for x in result_specs])
            self.client.post(endpoint, f"[{to_str}]")

    def download_agent_pushed_file(self, bundle: Bundle, download_path: str):
        bench_run_config = self.bench_run_config
        if bench_run_config.push_model:
            endpoint = f"/benchmarks/{self.bench_run_config.benchmark_id}/file/{bundle.id}"
            response = self.client.get(endpoint)
            save_response_to_file(response, download_path)


def save_response_to_file(response, output_file_path):
    if isinstance(response, StreamingResponse):

        async def write_chunks():
            with open(output_file_path, "wb") as f:
                async for chunk in response.body_iterator:
                    f.write(chunk)

        asyncio.run(write_chunks())
        logger.info(f"File saved to {output_file_path}")
    elif isinstance(response, requests.Response):
        if response.status_code == 200:
            with open(output_file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            logger.info(f"File downloaded successfully as: {output_file_path}")
        else:
            msg = f"Failed to download file: {response.status_code} - {response.text}"
            logger.error(msg)
            raise Exception(msg)
    else:
        raise ValueError("Response is not a StreamingResponse")
