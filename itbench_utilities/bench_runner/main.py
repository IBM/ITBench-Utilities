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

import argparse
import logging

import itbench_utilities.agent_harness.agent
import itbench_utilities.bench_runner.runner
from itbench_utilities.app.config import (
    DEFAULT_MINIBENCH_HOST,
    DEFAULT_MINIBENCH_PORT,
)
from itbench_utilities.common import log

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="IT-Bench Agent Benchmark Automation")
    parser.add_argument("-v", "--verbose", help="Display verbose output", action="count", default=0)

    subparsers = parser.add_subparsers(dest="command", required=True)

    # benchmark runner
    parser_runner = subparsers.add_parser("runner", description="Run benchmark runner ", help="see `runner -h`")
    parser_runner.add_argument("-c", "--config", type=str, help="Path to the application configuration.", required=True)
    parser_runner.add_argument("-i", "--runner_id", type=str, help="Unique identifier for the runner.", required=True)
    parser_runner.add_argument(
        "-t",
        "--service_type",
        type=str,
        help="Specify the service type identifier for the runner. This value must match an existing AgentType.",
    )
    parser_runner.add_argument(
        "--token",
        type=str,
        help="Specify the token to access the Bench Server.",
    )
    parser_runner.add_argument(
        "--single_run",
        action="store_true",
        help="Process one benchmark job and exit",
    )

    # caa agent harness
    parser_benchmark_agent = subparsers.add_parser(
        "minibench-agent", description="Benchmark an agent with MiniBehcn Server", help="see `minibench-agent -h`"
    )
    parser_benchmark_agent.add_argument(
        "--host", type=str, default=DEFAULT_MINIBENCH_HOST, help=f"The hostname or IP address (default: {DEFAULT_MINIBENCH_HOST})."
    )
    parser_benchmark_agent.add_argument(
        "--port", type=int, default=DEFAULT_MINIBENCH_PORT, help=f"The port number (default: {DEFAULT_MINIBENCH_PORT})."
    )
    parser_benchmark_agent.add_argument("-ad", "--agent_directory", type=str, default="caa-agent", help=f"Path to root directory of Agent project")
    parser_benchmark_agent.add_argument("-i", "--input", type=str, help="Path to MiniBenchResult", required=True)
    parser_benchmark_agent.add_argument("-c", "--config", type=str, help="Path to AgentHarness configuration")

    args = parser.parse_args()

    if args.verbose > 0:
        log.init(logging.DEBUG)
    else:
        log.init()

    if args.command == 'runner':
        itbench_utilities.bench_runner.runner.run(args)


if __name__ == "__main__":
    main()
