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
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List

from itbench_utilities.agent_operator import AgentOperator
from itbench_utilities.app.models.agent import Agent, AgentSpec
from itbench_utilities.app.models.base import AgentPhaseEnum, Metadata
from itbench_utilities.app.models.bundle import Env, MakeCmd
from itbench_utilities.app.utils import create_status, get_timestamp
from itbench_utilities.bench_client import BenchClient
from itbench_utilities.benchmark import Benchmark, write_for_leaderboard
from itbench_utilities.bundle_operator import BundleOperator
from itbench_utilities.models.agent import AgentInfo
from itbench_utilities.models.benchmark import (
    BenchConfig,
    BenchmarkResult,
    BenchRunConfig,
)
from itbench_utilities.models.bundle import (
    Bundle,
    BundleRequest,
    BundleResult,
    BundleStatus,
)
from itbench_utilities.observer import Observer, gen_json_logging_callback
from tests import bundle_statues

OUTPUT_DIR = Path(os.getenv("TEST_OUTPUT_DIR", "/tmp/itbench_utilities_test"))


def build_agent():
    return Agent(
        metadata=Metadata(id="abc", resource_type="agents", creation_timestamp=get_timestamp()),
        spec=AgentSpec(name="abc"),
        status=create_status(phase=AgentPhaseEnum.Ready),
    )


logger = logging.getLogger("observer")
observer = Observer()
observer.register(gen_json_logging_callback(logger))


class CallCount:
    def __init__(self):
        self.mock_error = 0


class Mock(ABC):

    def __init__(self, monkeypatch):
        self.monkeypatch = monkeypatch
        self.call_count = CallCount()

    def get_status(self) -> BundleStatus:
        pass

    def get_evaluation(self):
        pass

    def replace_get_status_method(self, bundle_statuses):
        results = iter(bundle_statuses)
        mock_get_bundle_status = lambda: next(results)
        self.monkeypatch.setattr(self, "get_status", mock_get_bundle_status)

    def mock_get(self, **kwargs):
        return json.dumps({})

    def mock_evaluate(self, **kwargs):
        self.replace_get_status_method([bundle_statues.FAULT_INJECTED])
        result = self.get_evaluation()
        return json.dumps(result)

    def mock_deploy_bundle(self, **kwargs):
        self.replace_get_status_method([bundle_statues.DEPLOYING, bundle_statues.DEPLOYED])

    def mock_inject_fault(self, **kwargs):
        self.replace_get_evaluation_method(lambda: {"pass": False, "report": []})
        self.replace_get_status_method([bundle_statues.FAULT_INJECTING, bundle_statues.FAULT_INJECTED, bundle_statues.FAULT_INJECTED])

    def replace_get_evaluation_method(self, callback, **kwargs):
        ret = callback(**kwargs)
        self.monkeypatch.setattr(self, "get_evaluation", lambda: ret)

    def mock_delete(self, **kwargs):
        self.replace_get_status_method([bundle_statues.DESTROYING, bundle_statues.DESTROYED])

    def mock_error(self, **kwargs):
        self.call_count.mock_error = self.call_count.mock_error + 1
        self.replace_get_status_method([bundle_statues.DESTROYING, bundle_statues.DESTROYED])

    def gen_mock_invoke_bundle(self):

        def mock_invoke_bundle(_self, target, extra_args=[], env={}, retry=0, max_retry=1, interval=1):
            _kwargs = {
                "_self": _self,
                "target": target,
                "extra_args": extra_args,
                "env": env,
                "retry": retry,
                "max_retry": max_retry,
                "interval": interval,
            }
            if target == "get_status":
                status_json = self.get_status().model_dump_json()
                data = {"status": json.loads(status_json)}
                return json.dumps(data)
            elif target == "get":
                return self.mock_get(**_kwargs)
            elif target == "evaluate":
                return self.mock_evaluate(**_kwargs)
            elif target == "deploy_bundle":
                return self.mock_deploy_bundle(**_kwargs)
            elif target == "inject_fault":
                return self.mock_inject_fault(**_kwargs)
            elif target == "delete":
                return self.mock_delete(**_kwargs)
            elif target == "on_error":
                return self.mock_error(**_kwargs)

        return mock_invoke_bundle

    @abstractmethod
    def mock_invoke_agent(self, **kwargs): ...

    def gen_mock_invoke_agent(self):
        def mock_invoke_agent(_self, bundle_name, shared_workspace, bundle_entity: Dict[str, Any], output_dir: Path):
            self.mock_invoke_agent(
                _self=_self,
                bundle_name=bundle_name,
                shared_workspace=shared_workspace,
                bundle_entity=bundle_entity,
                output_dir=output_dir,
            )

        return mock_invoke_agent


def evaluate_agent(mock: Mock, bundle_map: Dict[str, str]):
    monkeypatch = mock.monkeypatch
    monkeypatch.setattr(BundleOperator, "invoke_bundle", mock.gen_mock_invoke_bundle())

    monkeypatch.setattr(AgentOperator, "invoke_agent", mock.gen_mock_invoke_agent())

    monkeypatch.setattr(BenchClient, "get_agent_status", lambda self, agent_id: build_agent())

    bench_config = BenchConfig(title="test", is_test=True, soft_delete=False, resolution_wait=1)
    bundles = [
        Bundle(id="test", name=x, directory=".", incident_type="test", status=bundle_statues.INITIAL, polling_interval=1) for x in bundle_map.keys()
    ]
    agent = AgentInfo(id="test", name="agent1", directory="/tmp")
    ao = AgentOperator(agent)
    bos = [BundleOperator(bundle=x, bundle_request=BundleRequest(shared_workspace="/tmp/shared"), observer=observer) for x in bundles]
    bench_run_config = BenchRunConfig(
        benchmark_id="test", push_model=False, config=bench_config, agents=[agent], bundles=bundles, output_dir=OUTPUT_DIR.as_posix()
    )
    bundle_results = []
    for bo in bos:
        bench_client = BenchClient(bench_run_config=bench_run_config, user_id="")
        bundle_results = bundle_results + Benchmark(observer=observer).benchmark_per_bundle(ao, bo, bench_client, OUTPUT_DIR, bench_run_config)
    df = BundleResult.to_dataframe(bundle_results)
    df[BundleResult.Column.ttr] = df[BundleResult.Column.ttr].dt.total_seconds()

    for key, value in bundle_map.items():
        assert not df[(df[BundleResult.Column.name] == key) & (df[BundleResult.Column.passed] == value)].empty


def test_evaluate_agent(monkeypatch):
    class _Mock(Mock):
        def mock_invoke_agent(self, **kwargs):
            bundle_name = kwargs["bundle_name"]
            self.replace_get_evaluation_method(lambda: {"pass": bundle_map[bundle_name], "report": []})

    mock = _Mock(monkeypatch)
    bundle_map = {
        "bundle1": True,
        "bundle2": False,
    }
    evaluate_agent(mock, bundle_map)
    assert mock.call_count.mock_error == 0


def test_evaluate_agent_with_bundle_error(monkeypatch):
    bundle_map = {
        "bundle1": False,
        "bundle2": True,
    }

    class _Mock(Mock):
        def mock_invoke_agent(self, **kwargs):
            bundle_name = kwargs["bundle_name"]
            self.replace_get_evaluation_method(lambda: {"pass": bundle_map[bundle_name], "report": []})

        def mock_deploy_bundle(self, **kwargs):
            bo: BundleOperator = kwargs["_self"]
            if bo.bundle.name == "bundle1":
                deploy_error = bundle_statues.build(
                    [
                        ("Deployed", "False", "DeploymentFailed"),
                    ],
                    bundle_statues.DEPLOYING,
                )
                self.replace_get_status_method([bundle_statues.DEPLOYING, deploy_error])
            else:
                super().mock_deploy_bundle(**kwargs)

    mock = _Mock(monkeypatch)
    evaluate_agent(mock, bundle_map)
    assert mock.call_count.mock_error == 1


def run_benchmark(mock: Mock, bundles: List[str], agent_success_map: Dict[str, str]) -> List[BenchmarkResult]:
    bundles = [Bundle(id="test", name=x, directory=".", incident_type="test", status=bundle_statues.INITIAL, polling_interval=1) for x in bundles]
    return run_benchmark_with_bundles(mock, bundles, agent_success_map)


def run_benchmark_with_bundles(mock: Mock, bundles: List[Bundle], agent_success_map: Dict[str, str]) -> List[BenchmarkResult]:
    monkeypatch = mock.monkeypatch
    monkeypatch.setattr(BundleOperator, "invoke_bundle", mock.gen_mock_invoke_bundle())
    monkeypatch.setattr(AgentOperator, "invoke_agent", mock.gen_mock_invoke_agent())
    monkeypatch.setattr(BenchClient, "get_agent_status", lambda self, agent_id: build_agent())

    agents = [AgentInfo(id="test", name=x, directory=".") for x in agent_success_map.keys()]

    bench_config = BenchConfig(title="test", is_test=True, soft_delete=False, resolution_wait=1)
    bench_run_config = BenchRunConfig(
        benchmark_id="test", push_model=False, config=bench_config, agents=agents, bundles=bundles, output_dir=OUTPUT_DIR.as_posix()
    )
    benchmark_results = Benchmark(observer=observer).benchmark(bench_run_config)
    return benchmark_results


def test_benchmark(monkeypatch):

    bundles = ["bundle1", "bundle2"]

    agent_success_map = {
        "agent1": {"bundle1": False, "bundle2": True},
        "agent2": {"bundle1": False, "bundle2": False},
    }

    class _Mock(Mock):
        def mock_invoke_agent(self, **kwargs):
            ao: AgentOperator = kwargs["_self"]
            bundle_name = kwargs["bundle_name"]
            self.replace_get_evaluation_method(lambda: {"pass": agent_success_map[ao.agent_info.name][bundle_name], "report": []})

    mock = _Mock(monkeypatch)
    benchmark_results = run_benchmark(mock, bundles, agent_success_map)
    assert benchmark_results[0].agent == "agent1" and (benchmark_results[0].score > 0.49 and benchmark_results[0].score < 0.51)
    assert benchmark_results[1].agent == "agent2" and benchmark_results[1].score < 0.01
    write_for_leaderboard(benchmark_results, OUTPUT_DIR)
    assert mock.call_count.mock_error == 0


def test_benchmark_with_bundle_error(monkeypatch):

    bundles = ["bundle1", "bundle2"]

    agent_success_map = {
        "agent1": {"bundle1": False, "bundle2": True},
        "agent2": {"bundle1": False, "bundle2": False},
    }

    class _Mock(Mock):
        def mock_invoke_agent(self, **kwargs):
            ao: AgentOperator = kwargs["_self"]
            bundle_name = kwargs["bundle_name"]
            self.replace_get_evaluation_method(lambda: {"pass": agent_success_map[ao.agent_info.name][bundle_name], "report": []})

        def mock_deploy_bundle(self, **kwargs):
            bo: BundleOperator = kwargs["_self"]
            if bo.bundle.name == "bundle1":
                deploy_error = bundle_statues.build(
                    [
                        ("Deployed", "False", "DeploymentFailed"),
                    ],
                    bundle_statues.DEPLOYING,
                )
                self.replace_get_status_method([bundle_statues.DEPLOYING, deploy_error])
            else:
                super().mock_deploy_bundle(**kwargs)

    mock = _Mock(monkeypatch)
    bundles = [Bundle(id="test", name=x, directory=".", incident_type="test", status=bundle_statues.INITIAL, polling_interval=1) for x in bundles]
    benchmark_results = run_benchmark_with_bundles(mock, bundles, agent_success_map)
    # score to be 1.0 since consider only cases where errors do not happen.
    assert benchmark_results[0].agent == "agent1" and (benchmark_results[0].score > 0.99)
    assert benchmark_results[1].agent == "agent2" and benchmark_results[1].score < 0.01
    write_for_leaderboard(benchmark_results, OUTPUT_DIR)
    assert mock.call_count.mock_error == 2  # 1 bundle in each bench should be error
