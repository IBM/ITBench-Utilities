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

import logging
from typing import List, Optional

from itbench_utilities.app.models.agent import Agent as AgentInApp
from itbench_utilities.app.models.benchmark import Benchmark
from itbench_utilities.app.models.bundle import Bundle as BundleInApp
from itbench_utilities.app.utils import get_tempdir
from itbench_utilities.models.agent import AgentInfo
from itbench_utilities.models.benchmark import BenchConfig, BenchRunConfig
from itbench_utilities.models.bundle import Bundle

logger = logging.getLogger(__name__)


def build_benchmark_run_config(
    benchmark: Benchmark,
    agents: List[AgentInApp],
    bundles: List[BundleInApp],
    enable_safe_delete: Optional[bool] = False,
    interval: Optional[int] = None,
) -> BenchRunConfig:
    benchmark_id = benchmark.metadata.id
    agent_infos = [AgentInfo(id=x.metadata.id, name=x.spec.name, directory=x.spec.path if x.spec.path else "", mode=x.spec.mode) for x in agents]
    _bundles = [
        Bundle(
            id=x.metadata.id,
            name=x.spec.name,
            description=x.spec.description,
            incident_type=x.spec.scenario_type,
            bundle_ready_timeout=x.spec.bundle_ready_timeout,
            agent_operation_timeout=x.spec.agent_operation_timeout,
            directory=f"{x.spec.root_dir}/{x.spec.path}" if x.spec.root_dir else x.spec.path,
            params=x.spec.params,
            input=x.spec.data["input"] if x.spec.data and "input" in x.spec.data else None,
            env=x.spec.env,
            make_target_mapping=x.spec.make_target_mapping,
            enable_evaluation_wait=x.spec.enable_evaluation_wait,
            use_input_file=False,
        )
        for x in bundles
    ]

    bench_config = BenchConfig(title=benchmark.spec.name, is_test=False, soft_delete=enable_safe_delete)
    bench_run_config = BenchRunConfig(
        benchmark_id=benchmark_id,
        push_model=True,
        config=bench_config,
        agents=agent_infos,
        bundles=_bundles,
        output_dir=get_tempdir(benchmark_id),
        interval=interval,
    )
    return bench_run_config


def setup_request_logger(benchmark_id: str, debug=False) -> logging.Logger:
    logger = logging.getLogger(benchmark_id)
    log_format = logging.Formatter("[%(asctime)s %(levelname)s] %(message)s")
    log_file_name = f"log_{benchmark_id}.log"

    if logger.hasHandlers():
        logger.handlers.clear()

    file_handler = logging.FileHandler(log_file_name)
    if debug:
        file_handler.setLevel(logging.DEBUG)
    else:
        file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(log_format)
    logger.addHandler(file_handler)

    return logger


def get_specific_log_file_path(logger_instance, benchmark_id):
    for handler in logger_instance.handlers:
        if isinstance(handler, logging.FileHandler) and benchmark_id in handler.baseFilename:
            return handler.baseFilename
    return None
