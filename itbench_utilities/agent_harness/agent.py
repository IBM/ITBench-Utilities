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
import json
import logging
import traceback
from pathlib import Path
from typing import Any, List, Optional

import yaml
from pydantic import BaseModel

from itbench_utilities.agent_operator import AgentOperator
from itbench_utilities.app.models.agent import (
    Agent,
    AgentBenchmarkEntry,
    AgentManifest,
)
from itbench_utilities.app.models.base import (
    AgentPhaseEnum,
    BundlePhaseEnum,
    Status,
)
from itbench_utilities.app.models.bundle import Bundle
from itbench_utilities.app.utils import get_timestamp_iso
from itbench_utilities.common.rest_client import RestClient
from itbench_utilities.models.agent import AgentInfo, AgentRunCommand

logger = logging.getLogger(__name__)


class AgentHarnessConfig(BaseModel):
    run: Optional[AgentRunCommand] = None
    path_to_data_provided_by_scenario: Optional[str] = None
    path_to_data_pushed_to_scenario: Optional[str] = None


class AgentHarness:

    def __init__(
        self,
        agent_manifest: AgentManifest,
        agent_directory: str,
        host: str,
        port: int,
        root_path: Optional[str] = "",
        ssl: Optional[bool] = False,
        ssl_verify: Optional[bool] = False,
        config: Optional[AgentHarnessConfig] = None,
        single_run=False,
        interval=5,
        benchmark_timeout=300,
    ) -> None:
        self.agent_manifest = agent_manifest
        self.agent_directory = agent_directory
        self.host = host
        self.port = port
        self.config = config
        self.single_run = single_run
        self.interval = interval
        self.benchmark_timeout = benchmark_timeout
        self.rest_client = RestClient(
            self.host,
            self.port,
            headers={"Authorization": f"Bearer {self.agent_manifest.token}"},
            ssl=ssl,
            verify=ssl_verify,
            root_path=root_path,
        )
        self.stop_event = asyncio.Event()
        self.task_history = []

    async def run(self):

        timeout = 3600
        elapsed_time = 0
        while elapsed_time < timeout and not self.stop_event.is_set():
            entries: List[AgentBenchmarkEntry] = []
            try:
                manifest_endpoint = f"{self.agent_manifest.manifest_endpoint}"
                response = self.rest_client.get(manifest_endpoint)
                data = response.json()
                agent_manifest = AgentManifest.model_validate(data)
                entries = agent_manifest.benchmark_entries
            except Exception as e:
                logger.error(f"Failed to get manifests: {e}")

            logger.info(f"The number of benchmark entries: {len(entries)}")
            benchmatk_statuses = [f"{x.benchmark_id}: {x.status.phase}" for x in entries]
            logger.info(f"The benchmark statuses: {benchmatk_statuses}")

            entries = [x for x in entries if x.status.phase == AgentPhaseEnum.NotStarted]
            if len(entries) > 0:
                for benchmark_entry in entries:
                    benchmark_id = benchmark_entry.benchmark_id
                    logger.info(f"Take the benchmark '{benchmark_entry.benchmark_id}'")
                    self.add_history(benchmark_id)
                    self.rest_client.put(
                        f"{self.agent_manifest.manifest_endpoint}/benchmark-entries/{benchmark_id}",
                        Status(phase=AgentPhaseEnum.Executing).model_dump_json(),
                    )
                    is_completed = await self.run_benchmark(benchmark_id, benchmark_entry.agent_access_info.id)
                    if is_completed:
                        phase = AgentPhaseEnum.Finished
                    else:
                        phase = AgentPhaseEnum.TimeedOut
                    self.rest_client.put(
                        f"{self.agent_manifest.manifest_endpoint}/benchmark-entries/{benchmark_id}", Status(phase=phase).model_dump_json()
                    )
                if self.single_run:
                    logger.info("Task completed. Exiting due to run-once mode.")
                    await self.stop()
            else:
                logger.info(f"No benchmark entries with status 'NotStarted' found. Wait for {self.interval} seconds before the next check...")
            await asyncio.sleep(self.interval)
            elapsed_time += self.interval

    async def run_benchmark(self, benchmark_id, agent_id):

        timeout = self.benchmark_timeout
        elapsed_time = 0
        while not self.stop_event.is_set():

            if elapsed_time > timeout:
                logger.error("Timeout reached while waiting for targets to leave Ready phase.")
                break
            response = self.rest_client.get(f"/benchmarks/{benchmark_id}/bundles/")
            data = response.json()
            bundles = [Bundle.model_validate(x) for x in data]
            num_of_targets = len(bundles)

            ready_targets = [x for x in bundles if x.status.phase == BundlePhaseEnum.Ready]
            finished_targets = [x for x in bundles if x.status.phase in [BundlePhaseEnum.Terminated, BundlePhaseEnum.Error]]

            bundle_statuses = [f"{x.spec.name}:{x.status.phase}" for x in bundles]
            logger.info(f"The bundles status: {bundle_statuses}")

            if len(finished_targets) == num_of_targets:
                logger.info("All targets are finished.")
                return True

            if len(ready_targets) > 0:
                target = ready_targets[0]
                logger.info(f"Take '{target.spec.name}'")
                self.add_history(benchmark_id, target)
                await self.run_agent(target, benchmark_id, agent_id)
                logger.info(f"Finished '{target.spec.name}'")
            else:
                logger.info(f"Waiting for a target to be Ready phase...")

                await asyncio.sleep(self.interval)
                elapsed_time += self.interval

        return False

    async def run_agent(self, target_bundle: Bundle, benchmark_id: str, agent_id: str):
        response = self.rest_client.get(f"/benchmarks/{benchmark_id}/agents/{agent_id}")
        agent = Agent.model_validate(response.json())
        agent_info = AgentInfo(id=agent.metadata.id, name=agent.spec.name, directory=self.agent_directory)
        ao = AgentOperator(agent_info=agent_info)
        self.rest_client.assign(benchmark_id, agent_id, target_bundle.metadata.id)
        self.rest_client.push_agent_status(benchmark_id, agent_id, AgentPhaseEnum.Executing)
        try:
            shared_workspace = Path("/tmp") / "shared_workspace" / agent.metadata.id / target_bundle.spec.name
            shared_workspace.mkdir(parents=True, exist_ok=True)
            output_dir_per_bundle = Path("/tmp") / "output" / agent.metadata.id / target_bundle.spec.name
            output_dir_per_bundle.mkdir(parents=True, exist_ok=True)
            if self.config and self.config.run:
                path = Path(self.config.path_to_data_provided_by_scenario).absolute()
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("w") as f:
                    f.write(json.dumps(target_bundle.spec.data))
                stdout = ao.invoke_by_cmd(target_bundle.spec.name, self.config.run)
                self.rest_client.upload_file(benchmark_id, self.config.path_to_data_pushed_to_scenario, target_bundle.metadata.id)
            else:
                stdout = ao.invoke_agent(target_bundle.spec.name, shared_workspace, target_bundle.spec.data, output_dir_per_bundle)
            self.add_history(benchmark_id, target_bundle, stdout)
            self.rest_client.push_agent_status(benchmark_id, agent_id, AgentPhaseEnum.Finished, message=stdout)
        except Exception as e:
            err = traceback.format_exc()
            logger.error(err)
            self.rest_client.push_agent_status(benchmark_id, agent_id, AgentPhaseEnum.Error, message=f"{e}")

        def wait_bundle_finished():
            logger.info(f"Wait for bundle to finish...")
            response = self.rest_client.get(f"/benchmarks/{benchmark_id}/bundles/{target_bundle.metadata.id}")
            data = response.json()
            bundle = Bundle.model_validate(data)
            if bundle.status.phase in [BundlePhaseEnum.Terminated, BundlePhaseEnum.Error]:
                return True
            return False

        await self.wait(wait_bundle_finished, timeout=30, interval=self.interval)
        self.rest_client.push_agent_status(benchmark_id, agent_id, AgentPhaseEnum.Ready)

    async def wait(self, callback, timeout=300, interval=10):
        elapsed_time = 0
        while elapsed_time < timeout and not self.stop_event.is_set():
            if callback():
                return
            await asyncio.sleep(interval)
            elapsed_time += self.interval

    async def stop(self):
        logger.info(f"Stopping agent runner...")
        self.stop_event.set()

    def add_history(self, benchmark_id: str, bundle: Optional[Bundle] = None, agent_output: Optional[Any] = None):
        item = {
            "benchmark_id": benchmark_id,
            "bundle_id": bundle.metadata.id if bundle else "",
            "bundle": bundle,
            "agent_output": agent_output,
            "timestamp": get_timestamp_iso(),
        }
        self.task_history.append(item)


def run(args):
    with open(args.input) as f:
        agent_manifest = AgentManifest.model_validate_json(f.read())

    config = None
    if args.config:
        with open(args.config) as f:
            data = yaml.safe_load(f.read())
            config = AgentHarnessConfig.model_validate(data)

    agent_harness = AgentHarness(
        agent_manifest,
        args.agent_directory,
        args.host,
        args.port,
        ssl=args.ssl,
        ssl_verify=args.ssl_verify,
        root_path=args.root_path,
        benchmark_timeout=args.benchmark_timeout,
        config=config,
        single_run=args.single_run,
    )
    asyncio.run(agent_harness.run())
