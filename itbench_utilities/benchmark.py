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

import json
import logging
import shutil
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import DefaultDict, Dict, List, Optional
from uuid import uuid4

import pandas as pd
from pydantic import BaseModel

import itbench_utilities.observer
from itbench_utilities.agent_operator import AgentOperator
from itbench_utilities.app.models.base import AgentPhaseEnum, BundlePhaseEnum
from itbench_utilities.bechmark_analyzer import Analyzer
from itbench_utilities.bench_client import BenchClient, BenchNotFoundException
from itbench_utilities.bundle_operator import BundleError, BundleOperator
from itbench_utilities.common.rest_client import RestClient
from itbench_utilities.models.agent import AgentInfo
from itbench_utilities.models.benchmark import (
    BenchConfig,
    BenchmarkResult,
    BenchRunConfig,
)
from itbench_utilities.models.bundle import (
    Bundle,
    BundleInfo,
    BundleRequest,
    BundleResult,
)
from itbench_utilities.observer import Observer

logger = logging.getLogger(__name__)
log_format = "[%(asctime)s %(levelname)s %(name)s] %(message)s"


class Benchmark:

    def __init__(self, observer: Optional[Observer] = None, _logger: Optional[logging.Logger] = None) -> None:
        self.logger = _logger if _logger else None
        self.observer = observer if observer else itbench_utilities.observer.DEFAULT_OBSERVER

    def get_logger(self) -> logging.Logger:
        return self.logger if self.logger else logger

    def run_benchmark_cmd(self, args):
        bench_config = BenchConfig(
            title=args.title,
            is_test=args.test,
            soft_delete=args.soft_delete,
            resolution_wait=args.resolution_wait,
        )
        agents = args.agents if args.agents else ["builtin", "human"]
        agent_dir = args.agent_dir
        agents = [AgentInfo(id=str(uuid4()), name=x, directory=agent_dir) for x in agents]

        bundles = args.bundles
        bundle_dir = args.bundle_dir
        if bundles[0] == '*':
            bundles = [Bundle(id=str(uuid4()), name=x.name, directory=x.as_posix()) for x in Path(bundle_dir).glob("*")]
        else:
            bundles = [Bundle(id=str(uuid4()), name=x, directory=f"{bundle_dir}/{x}") for x in bundles]
        for b in bundles:
            b.enable_evaluation_wait = True
        bench_run_config = BenchRunConfig(benchmark_id=str(uuid4()), config=bench_config, agents=agents, bundles=bundles, output_dir=args.out)
        self.run_benchmark(bench_run_config)

    def run_benchmark(self, bench_run_config: BenchRunConfig, rest_client: Optional[RestClient] = None, user_id: Optional[str] = None):
        output_dir = Path(bench_run_config.output_dir)

        benchmark_results = self.benchmark(bench_run_config, rest_client, user_id=user_id)
        write_for_leaderboard(benchmark_results, output_dir)

    def benchmark(
        self, bench_run_config: BenchRunConfig, rest_client: Optional[RestClient] = None, user_id: Optional[str] = None
    ) -> List[BenchmarkResult]:
        logger = self.get_logger()
        agents = bench_run_config.agents
        bundles = bench_run_config.bundles
        output_dir = Path(bench_run_config.output_dir).absolute()
        bench_config = bench_run_config.config
        grouped_bundles_by_agent = self.setup(agents, bundles, output_dir, bench_config)
        benchmark_results: List[BenchmarkResult] = []

        agent_names = ",".join([x.agent_info.name for x in grouped_bundles_by_agent.keys()])
        logger.info(f"Start benchmarking '[{agent_names}]'")
        for ao, bos in grouped_bundles_by_agent.items():
            output_dir_per_agent = output_dir / ao.agent_info.name
            output_dir_per_agent.mkdir(parents=True, exist_ok=True)
            bundle_names = ",".join([x.bundle.name for x in bos])
            logger.info(f"Benchmark '{ao.agent_info.name}' by scenarios '[{bundle_names}]'")
            bundle_results: List[BundleResult] = []
            for bo in bos:
                try:
                    logger.info(f" Run scenario '{bo.bundle.name}'", extra={"agent": ao.agent_info.name})
                    bench_client = BenchClient(bench_run_config=bench_run_config, rest_client=rest_client, user_id=user_id)
                    bench_client.validate_benchmark()
                    brs = self.benchmark_per_bundle(ao, bo, bench_client, output_dir_per_agent, bench_run_config)
                    bench_client.upload_bundle_results(bo.bundle, brs)

                    bundle_results = bundle_results + brs
                except BenchNotFoundException as e:
                    logger.error("Benchmark not found. This might happen if someone deleted the benchmark. " "Exception details: %s", str(e))
                    break
                except Exception as e:
                    logger.error(f"Unhandle exception happens, ignore it, and go next: {e}")

            logger.info(f"Finished benchmarking '{ao.agent_info.name}' by scenarios '{bundle_names}'")
            print(to_summary_table(bundle_results))

            analyzer = Analyzer(bundle_results)
            benchmark_result = analyzer.to_benchmark_result(bench_config.title, ao.agent_info.name)
            benchmark_results.append(benchmark_result)

        logger.info("Finished benchmarking for all agents.")

        return benchmark_results

    def setup(
        self, agents: List[AgentInfo], bundles: List[Bundle], output_dir: Path, bench_config: BenchConfig
    ) -> Dict[AgentOperator, List[BundleOperator]]:
        agent_bundle_pairs = []
        for agent in agents:
            if self.get_logger():
                ao = AgentOperator(agent, _logger=self.get_logger())
            else:
                ao = AgentOperator(agent)
            for bundle in bundles:
                info_path = bundle.get_path() / "info.json"
                if info_path.exists():
                    with info_path.open("r") as f:
                        info = BundleInfo.model_validate_json(f.read())
                        bundle.description = bundle.description if bundle.description else info.description
                        bundle.incident_type = bundle.incident_type if bundle.incident_type else info.incident_type
                timestamp = get_timestamp()
                shared_workspace = Path("/tmp") / agent.name / f"{bundle.name}_{timestamp}"
                shared_workspace.mkdir(parents=True, exist_ok=True)
                br = BundleRequest(shared_workspace=shared_workspace.as_posix())

                if bundle.use_input_file:
                    default_input = None
                    input_file = bundle.get_path() / "input.json"
                    if input_file.exists():
                        with input_file.open("r") as f:
                            default_input = json.load(f)
                    input = (
                        merge_dicts_recursively(default_input, bundle.input)
                        if default_input and bundle.input
                        else default_input or bundle.input or None
                    )
                    if input:
                        input["shared_workspace"] = shared_workspace.as_posix()
                        updated_input_file = shared_workspace / ".input.json"
                        updated_input_file.parent.mkdir(parents=True, exist_ok=True)
                        with updated_input_file.open("w") as f:
                            json.dump(input, f, indent=2)
                        br.input_file = updated_input_file.as_posix()
                        dump = output_dir / agent.name / bundle.name / "input.json"
                        dump.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy(updated_input_file, dump)

                if self.get_logger():
                    bo = BundleOperator(bundle, br, observer=self.observer, is_test=bench_config.is_test, _logger=self.get_logger())
                else:
                    bo = BundleOperator(bundle, br, observer=self.observer, is_test=bench_config.is_test)

                agent_bundle_pairs.append((ao, bo))

        grouped: DefaultDict[AgentOperator, List[BundleOperator]] = defaultdict(list)
        for x, y in agent_bundle_pairs:
            grouped[x].append(y)
        grouped_bundles_by_agent = dict(grouped)

        return grouped_bundles_by_agent

    def benchmark_per_bundle(
        self,
        agent_operator: AgentOperator,
        bundle_operator: BundleOperator,
        bench_client: BenchClient,
        output_dir: Path,
        bench_run_config: BenchRunConfig,
    ):
        logger = self.get_logger()

        self.observer.notify(
            "benchmark_per_bundle:start",
            {
                "agent_info": agent_operator.agent_info,
                "bundle": bundle_operator.bundle,
                "bundle_request": bundle_operator.bundle_request,
                "output_dir": output_dir,
                "bench_run_config": bench_run_config,
            },
        )
        bench_config = bench_run_config.config
        output_dir_per_bundle = output_dir / bundle_operator.bundle.name
        output_dir_per_bundle.mkdir(parents=True, exist_ok=True)

        bundle_results: List[BundleResult] = []
        ao = agent_operator
        agent = ao.agent_info
        bo = bundle_operator
        bundle = bo.bundle
        bundle_id = bo.bundle.id

        # Set bundle params for SRE
        if bundle.incident_type == "SRE":
            bo.bundle.params["RUN_UUID"] = bench_run_config.benchmark_id
            bo.bundle.params["PARTICIPANT_AGENT_UUID"] = ao.agent_info.id

        try:

            bench_client.push_bundle_status(bundle_id, BundlePhaseEnum.Provisioning)
            bo.deploy_bundle()
            bench_client.push_bundle_status(bundle_id, BundlePhaseEnum.Provisioned)

            bench_client.push_bundle_status(bundle_id, BundlePhaseEnum.FaultInjecting)
            bo.inject_fault()
            bench_client.push_bundle_status(bundle_id, BundlePhaseEnum.FaultInjected)

            timestamp_before = datetime.now(timezone.utc)

            # TODO: Need generalization to support other bundles, agents
            bundle_entity = bo.get_bundle()
            bundle_entity["shared_workspace"] = bo.bundle_request.shared_workspace
            bench_client.push_bundle_data(bundle_id, bundle_entity)
            bench_client.push_bundle_status(bundle_id, BundlePhaseEnum.Ready)

            agent_result: WaitAgentResult
            agent_remote_mode = ao.agent_info.mode and ao.agent_info.mode == "remote"
            if agent_remote_mode:
                agent_result = self.wait_for_agent_status(
                    bench_client, ao.agent_info.id, timeout=bundle.bundle_ready_timeout, timeout_of_execution=bundle.agent_operation_timeout
                )
            else:
                bench_client.push_agent_status(ao.agent_info.id, AgentPhaseEnum.Executing)

                try:
                    stdout = ao.invoke_agent(bo.bundle.name, bo.bundle_request.shared_workspace, bundle_entity, output_dir_per_bundle)
                    bench_client.push_agent_status(ao.agent_info.id, AgentPhaseEnum.Finished, message=stdout)
                    agent_result = WaitAgentResult(success=True)
                except Exception as e:
                    logger.error(e)
                    bench_client.push_agent_status(ao.agent_info.id, AgentPhaseEnum.Error, message=f"{e}")
                    agent_result = WaitAgentResult(success=False, message=f"{e}")

            timestamp_after = datetime.now(timezone.utc)
            ttr = timestamp_after - timestamp_before

            resolved = False

            if agent_result.success:
                try:
                    bench_client.download_agent_pushed_file(bundle, f"{bo.bundle_request.shared_workspace}/agent_output.data")
                except Exception as e:
                    logger.error(e)
                bench_client.push_bundle_status(bundle_id, BundlePhaseEnum.Evaluating)
                # TODO: Address time lag on the incident report to be up to date
                if bo.bundle.enable_evaluation_wait:
                    bo.wait_for_violation_resolved(timeout=bench_config.resolution_wait, interval=bo.bundle.polling_interval)
                evaluation = bo.evaluate()
                resolved = evaluation.pass_
                bench_client.push_bundle_status(bundle_id, BundlePhaseEnum.Evaluated)
                bundle_result = self.build_result(agent, bundle, resolved, ttr, message=evaluation.details)
            else:
                bench_client.push_bundle_status(bundle_id, BundlePhaseEnum.Error, message=agent_result.message)
                bundle_result = self.build_error_result(agent, bundle, f"Agent failed: {agent_result.message}", ttr=ttr)

            if bench_config.soft_delete:
                bo.delete_bundle(soft_delete=True)
                bench_client.push_bundle_status(bundle_id, BundlePhaseEnum.Terminating)
            else:
                bo.delete_bundle()
                bench_client.push_bundle_status(bundle_id, BundlePhaseEnum.Terminating)

            bench_client.push_bundle_status(bundle_id, BundlePhaseEnum.Terminated)

            if agent_remote_mode:
                agent_result = self.wait_for_agent_to_move_next(bench_client, ao.agent_info.id, timeout=bundle.bundle_ready_timeout)
                if not agent_result.success:
                    bundle_result.errored = True
                    bundle_result.message = "Agent status did not change Finished to Ready."
            bundle_results.append(bundle_result)
        except (BundleError, Exception) as e:
            if isinstance(e, BundleError):
                message = e.message
            else:
                message = str(e)
            error_action_message = bo.error_action()
            if error_action_message:
                message = message + "\n" + str(error_action_message)
            bundle_result = self.build_error_result(agent, bundle, message)
            bundle_results.append(bundle_result)
            bench_client.push_bundle_status(bundle_id, BundlePhaseEnum.Error, message)

        o = output_dir_per_bundle / "bundle-result.json"
        logger.info(f"Write to {o.as_posix()}")
        with o.open("w") as f:
            f.write(bundle_result.model_dump_json(indent=2))
        logger.info(f"{BundleResult.to_dataframe(bundle_results).to_markdown(index=False)}")

        return bundle_results

    def build_result(
        self, agent: AgentInfo, bundle: Bundle, _pass: bool, ttr: timedelta, message: Optional[str] = None, error: bool = False
    ) -> BundleResult:
        if message == None:
            message = ""
        return BundleResult(
            agent=agent.name,
            name=bundle.name,
            incident_type=bundle.incident_type,
            description=bundle.description,
            passed=_pass,
            ttr=ttr,
            errored=error,
            message=message,
            date=datetime.now(timezone.utc),
        )

    def build_error_result(self, agent: AgentInfo, bundle: Bundle, message: str, ttr=timedelta(seconds=0)) -> BundleResult:
        return self.build_result(agent, bundle, False, ttr, message=message, error=True)

    def wait_for_agent_status(
        self, bench_client: BenchClient, agent_id: str, timeout=300, timeout_of_execution=300, interval=10
    ) -> 'WaitAgentResult':
        logger = self.get_logger()
        elapsed_time = 0
        elapsed_time_of_execution = 0

        while elapsed_time < timeout:
            res = bench_client.get_agent_status(agent_id)
            phase = res.status.phase

            if phase == AgentPhaseEnum.Finished:
                logger.info("Operation completed successfully!")
                return WaitAgentResult(success=True)

            elif phase == AgentPhaseEnum.Executing:
                logger.info("Agent is working, waiting for it to finish...")
                elapsed_time = 0
                elapsed_time_of_execution += interval
                if elapsed_time_of_execution >= timeout_of_execution:
                    message = "Timeout reached for executing phase."
                    logger.error(message)
                    return WaitAgentResult(success=False, message=message)

            elif phase == AgentPhaseEnum.Error:
                message = "Agent encountered an error."
                logger.error(message)
                return WaitAgentResult(success=False, message=message)

            elif phase == AgentPhaseEnum.Ready:
                logger.info("Agent has started, monitoring its progress.")

            elif phase == AgentPhaseEnum.NotStarted:
                logger.info("Agent has not started.")

            else:
                logger.warning(f"Unexpected phase encountered: {phase}")

            time.sleep(interval)
            elapsed_time += interval

        message = "Timeout reached. The operation is still pending."
        logger.error(message)
        return WaitAgentResult(success=False, message=message)

    def wait_for_agent_to_move_next(self, bench_client: BenchClient, agent_id: str, timeout=300, interval=10) -> 'WaitAgentResult':
        logger = self.get_logger()
        elapsed_time = 0

        while elapsed_time < timeout:
            res = bench_client.get_agent_status(agent_id)
            phase = res.status.phase

            if phase == AgentPhaseEnum.Ready:
                logger.info("Agent is ready")
                return WaitAgentResult(success=True)

            time.sleep(interval)
            elapsed_time += interval

        message = "Timeout reached. The Agent could not be ready within the timeout."
        logger.error(message)
        return WaitAgentResult(success=False, message=message)


class WaitAgentResult(BaseModel):
    success: bool
    message: Optional[str] = None


def to_summary_table(bundle_results: List[BundleResult]) -> str:
    summary_df = BundleResult.to_dataframe(bundle_results)
    summary_df = summary_df.drop(columns=[BundleResult.Column.description, BundleResult.Column.agent, BundleResult.Column.message])
    summary_df[BundleResult.Column.ttr] = summary_df[BundleResult.Column.ttr].dt.total_seconds()
    summary_df = summary_df.rename(
        columns={
            BundleResult.Column.name: "scenario",
            BundleResult.Column.incident_type: "scenario type",
        }
    )
    return summary_df.to_markdown(index=False)


def build_benchmark_df(benchmark_results: List[BenchmarkResult]) -> pd.DataFrame:
    df = BenchmarkResult.to_dataframe(benchmark_results, exclude=[BenchmarkResult.Column.results])
    if not df.empty:
        df[BenchmarkResult.Column.mttr] = df[BenchmarkResult.Column.mttr].dt.total_seconds()
        df = df.sort_values(by=BenchmarkResult.Column.score, ascending=False)
    return df


def build_bundles_df(bundle_results: List[BundleResult]) -> pd.DataFrame:
    df = BundleResult.to_dataframe(bundle_results)
    if not df.empty:
        df[BundleResult.Column.ttr] = df[BundleResult.Column.ttr].dt.total_seconds()
    return df


def write_for_leaderboard(benchmark_results: List[BenchmarkResult], output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    path_bundle_results = output_dir / "bundle_results.jsonl"
    path_bundle_results.unlink(missing_ok=True)

    path_bench_results = output_dir / "benchmark_results.jsonl"
    path_bench_results_md = output_dir / "benchmark_results.md"

    for br in benchmark_results:
        df = build_bundles_df(br.results)
        jsonline = df.to_json(orient="records", lines=True, date_format="iso")
        with path_bundle_results.open("a") as f:
            f.write(jsonline)

    df = build_benchmark_df(benchmark_results)
    with path_bench_results.open("w") as f:
        f.write(df.to_json(orient="records", lines=True, date_format="iso"))

    df = df.reindex(
        columns=[
            BenchmarkResult.Column.agent,
            BenchmarkResult.Column.incident_type,
            BenchmarkResult.Column.score,
            BenchmarkResult.Column.mttr,
            BenchmarkResult.Column.date,
        ]
    )
    df[BenchmarkResult.Column.score] = df[BenchmarkResult.Column.score] * 100
    df = df.rename(columns={BenchmarkResult.Column.incident_type: "scenario type", BenchmarkResult.Column.score: "pass rate (%)"})
    md = df.to_markdown(index=False)
    print(md)
    with path_bench_results_md.open("w") as f:
        f.write(md)


def merge_dicts_recursively(dict_a, dict_b):
    result = dict_a.copy()
    for key, value in dict_b.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts_recursively(result[key], value)
        else:
            result[key] = value
    return result


def get_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")
