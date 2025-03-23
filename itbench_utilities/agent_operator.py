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
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from jinja2 import Template

from itbench_utilities.models.agent import AgentInfo, AgentRunCommand

logger = logging.getLogger(__name__)


class AgentOperator:

    def __init__(self, agent_info: AgentInfo, _logger: Optional[logging.Logger] = None) -> None:
        self.agent_info = agent_info
        self.logger = _logger if _logger else logger

    def invoke_by_cmd(self, bundle_name: str, run_command: AgentRunCommand) -> str:
        logger = self.logger

        logger.info(f"Invoke Agent by provided command for '{bundle_name}'...")
        cwd = f"{self.agent_info.directory}"
        cmd = run_command.command
        if run_command.args:
            cmd = cmd + run_command.args
        cmd = " ".join(cmd)
        logger.info(f"Command: {cmd}")

        env = None
        if run_command.env:
            env = [dict([x.name, x.value]) for x in run_command.env]
        stdout, stderr = self.run_cmd(cwd, env, cmd)
        logger.info(f"Finish Agent tasks for '{bundle_name}'...")
        if stderr:
            raise Exception(stderr)

        return stdout

    def invoke_agent(self, bundle_name: str, shared_workspace: str, bundle_entity: Dict[str, Any], output_dir: Path) -> str:
        logger = self.logger

        logger.info(f"Invoke Agent for '{bundle_name}'...")

        opath = output_dir / "agent-result.json"
        goal_template_str = bundle_entity["goal_template"]
        goal_template = Template(goal_template_str)
        vars = bundle_entity.get("vars", {})
        kubeconfig = vars.get("kubeconfig")
        agent_kubeconfig = Path(shared_workspace) / "kubeconfig.yaml"
        with agent_kubeconfig.open("w") as f:
            f.write(kubeconfig)
        goal = goal_template.render(shared_workspace=shared_workspace, kubeconfig=agent_kubeconfig.as_posix())
        logger.info("Goal:\n" + goal)
        goal = goal.replace("`", "\\`")
        cwd = f"{self.agent_info.directory}"
        cmd = f"source .venv/bin/activate; python src/ciso_agent/main.py --goal \"{goal}\" --auto-approve -o {opath.as_posix()}"
        logger.info(f"Command: {cmd}")
        stdout, stderr = self.run_cmd(cwd, None, cmd)

        try:
            shutil.copytree(shared_workspace, output_dir / "shared_workspace", dirs_exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to copy chared working directory to log directory: {e}")

        logger.info(f"Finish Agent tasks for '{bundle_name}'...")

        if stderr:
            raise Exception(stderr)

        return stdout

    def run_cmd(self, cwd, env: Optional[Dict[str, str]] = None, *argv) -> Tuple[Optional[str], Optional[str]]:
        logger = self.logger

        current_env = os.environ.copy()
        if env:
            current_env.update(env)

        process = subprocess.Popen(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            cwd=cwd,
            env=current_env,
            shell=True,
        )

        stdout = ''
        for stdout_line in process.stdout:
            stdout += stdout_line
            logger.info(stdout_line.strip())

        for stderr_line in process.stderr:
            logger.error(stderr_line.strip())

        process.stdout.close()
        process.stderr.close()
        process.wait()

        if process.returncode != 0:
            stderr = process.stderr.read()
            logger.error(f"An error occurred. Return code: {process.returncode}")
            logger.error(stderr)
            return (None, stderr)
        return (stdout, None)
