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
from pathlib import Path
from typing import Optional

import yaml

import itbench_utilities.benchmark
from itbench_utilities.app.config import AppConfig, get_service_api_key
from itbench_utilities.app.models.agent import Agent as AgentInApp
from itbench_utilities.app.models.agent import AgentManifest
from itbench_utilities.app.models.base import BenchmarkPhaseEnum
from itbench_utilities.app.models.benchmark import (
    Benchmark,
    BenchmarkJob,
    BenchmarkJobTake,
)
from itbench_utilities.app.models.bundle import Bundle as BundleInApp
from itbench_utilities.bench_runner.utils import (
    build_benchmark_run_config,
    get_specific_log_file_path,
    setup_request_logger,
)
from itbench_utilities.app.utils import create_status
from itbench_utilities.common.rest_client import RestClient

logger = logging.getLogger(__name__)


class BenchmarkRunner:
    def __init__(
        self,
        app_config: AppConfig,
        runner_id: str,
        service_type: Optional[str] = None,
        token: Optional[str] = None,
        single_run=False,
        interval=10,
    ) -> None:
        self.app_config = app_config
        self.runner_id = runner_id
        self.host = app_config.host
        self.port = app_config.port
        self.ssl = app_config.ssl_enabled
        self.ssl_verify = app_config.ssl_verify
        self.max_concurrent_tasks = 1
        self.running_tasks = 0
        self.interval = interval
        self.service_type = service_type
        self.token = token
        self.single_run = single_run
        self.job_client: RestClient
        self.stop_event = asyncio.Event()

    def init_job_client(self):
        self.job_client = RestClient(self.host, self.port, ssl=self.ssl, verify=self.ssl_verify)
        self.auth_job_client()

    def auth_job_client(self):
        if self.service_type:
            service_accounts = [x for x in self.app_config.service_accounts if x.type == self.service_type]
            if len(service_accounts) == 0:
                logger.error("Please specify correct service type")
            service_account = service_accounts[0]
            self.job_client.login(service_account.id, get_service_api_key(service_account.id))
        elif self.token:
            self.job_client.headers["Authorization"] = f"Bearer {self.token}"

    def create_finished_status(self):
        return create_status(phase=BenchmarkPhaseEnum.Finished)

    async def run(self):

        self.init_job_client()

        while not self.stop_event.is_set():
            if self.running_tasks < self.max_concurrent_tasks:
                logger.info("Fetch benchmark jobs...")
                self.auth_job_client()
                response = self.job_client.get("/benchmarks/queue/list_benchmark_jobs")
                data = response.json()
                jobs = [BenchmarkJob.model_validate(x) for x in data]
                if len(jobs) == 0:
                    logger.info(f"There are no benchmark jobs. Wait for '{self.interval}s' the next poll..")
                for job in jobs:
                    benchmark_id = job.benchmark.metadata.id
                    body = BenchmarkJobTake(runner_id=self.runner_id)
                    response = self.job_client.put(f"/benchmarks/{benchmark_id}/take_benchmark_job", body=body.model_dump_json())
                    data = response.json()
                    if data["success"] == True:
                        job.benchmark.spec.runner_id = self.runner_id  # TODO: fix to get the latest job from server
                        logger.info(f"Benchmark job '{benchmark_id}' is successfully taken. Start benchmark...")
                        self.running_tasks += 1
                        asyncio.create_task(self.run_benchmark(job.benchmark, job.agent_manifest))
                        break
                    else:
                        logger.info(f"Benchmark job '{benchmark_id}' is already assigned.")
                if self.single_run and self.running_tasks < 1:
                    logger.info("Task completed. Exiting due to run-once mode.")
                    await self.stop()
            else:
                logger.info("The number of current task is over max concurrent jobs. Wait for the runner to be available.")
            await asyncio.sleep(self.interval)

    async def run_benchmark(self, benchmark: Benchmark, agent_manifest: AgentManifest):
        benchmark_id = benchmark.metadata.id
        token = agent_manifest.token
        headers = {"Authorization": f"Bearer {token}"}
        client = RestClient(self.host, self.port, headers=headers, ssl=self.ssl, verify=self.ssl_verify)
        base_endpoint = f"/benchmarks/{benchmark_id}"
        try:
            response = client.get(f"{base_endpoint}/bundles")
            _bundles = [BundleInApp.model_validate(x) for x in response.json()]

            response = client.get(f"{base_endpoint}/agents")
            _agents = [AgentInApp.model_validate(x) for x in response.json()]

            bench_run_config = build_benchmark_run_config(
                benchmark,
                _agents,
                _bundles,
                self.app_config.enable_soft_delete,
                self.interval,
            )

            _logger = setup_request_logger(benchmark_id)
            logfilepath = get_specific_log_file_path(_logger, benchmark_id)
            benchmark_runner = itbench_utilities.benchmark.Benchmark(_logger=_logger)

            benchmark.status = create_status(phase=BenchmarkPhaseEnum.Running)
            benchmark.spec.log_file_path = logfilepath
            client.put(f"{base_endpoint}/update_benchmark_job", benchmark.model_dump_json())
            await asyncio.to_thread(benchmark_runner.run_benchmark, bench_run_config, client)

            benchmark.status = self.create_finished_status()
            client.put(f"{base_endpoint}/update_benchmark_job", benchmark.model_dump_json())
            logger.info("Benchmarking is finished")
            self.running_tasks -= 1
        except Exception as e:
            message = f"Error while running benchmark '{benchmark.metadata.id}': {e}"
            logger.error(message)
            self.running_tasks -= 1
            benchmark.status = create_status(phase=BenchmarkPhaseEnum.Error, message=message)
            try:
                response = self.job_client.put(f"/benchmarks/{benchmark_id}/release_benchmark_job")
                if not response.json()["success"]:
                    raise Exception(f"{response.text}")
            except Exception as e:
                message = f"Failed to release job of benchmark id '{benchmark.metadata.id}': {e}"
                logger.error(message)
                benchmark.status.message = benchmark.status.message + "\n" + message
            try:
                client.put(f"{base_endpoint}/update_benchmark_job", benchmark.model_dump_json())
            except Exception as e:
                logger.error(f"Failed to update status of benchmark id '{benchmark.metadata.id}': {e}")

    async def stop(self):
        logger.info(f"Stopping benchmark runner...")
        self.stop_event.set()


def run(args):

    config_path = args.config
    with Path(config_path).open("r") as f:
        data = yaml.safe_load(f)
        app_config = AppConfig.model_validate(data)
    runner = BenchmarkRunner(app_config, args.runner_id, args.service_type, args.token, single_run=args.single_run)
    asyncio.run(runner.run())
