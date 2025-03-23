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
import subprocess
import time
from typing import Any, Dict, Optional

from itbench_utilities.app.models.bundle import MakeCmd, MakeTargetMapping
from itbench_utilities.models.bundle import (
    Bundle,
    BundleEvaluation,
    BundleRequest,
    BundleStatus,
)
from itbench_utilities.observer import Observer

DEFAULT_WAIT_INTERVAL = int(os.getenv("DEFAULT_WAIT_INTERVAL", "5"))
DEFAULT_WAIT_TIMEOUT = int(os.getenv("DEFAULT_WAIT_TIMEOUT", "300"))
DEFAULT_RETRY_INTERVAL = int(os.getenv("DEFAULT_RETRY_INTERVAL", "5"))
DEFAULT_MAX_RETRY = int(os.getenv("DEFAULT_MAX_RETRY", "3"))

logger = logging.getLogger(__name__)
log_format = "[%(asctime)s %(levelname)s %(name)s] %(message)s"


class BundleOperator:

    def __init__(
        self,
        bundle: Bundle,
        bundle_request: BundleRequest,
        observer: Observer,
        is_test: bool = False,
        _logger: Optional[logging.Logger] = None,
    ) -> None:
        self.bundle = bundle
        self.bundle_request = bundle_request
        self.observer = observer
        self.is_test = is_test
        self.logger = _logger if _logger else logger
        self.make_targets = self.bundle.make_target_mapping
        deploy = MakeCmd(target="deploy_bundle")
        inject_fault = MakeCmd(target="inject_fault")
        evaluate = MakeCmd(target="evaluate")
        delete = MakeCmd(target="delete")
        revert = MakeCmd(target="revert")
        get = MakeCmd(target="get")
        status = MakeCmd(target="get_status")
        on_error = MakeCmd(target="on_error")

        if not self.make_targets:
            self.make_targets = MakeTargetMapping(
                deploy=deploy, inject_fault=inject_fault, evaluate=evaluate, delete=delete, revert=revert, get=get, status=status, on_error=on_error
            )
        self.make_targets.deploy = self.make_targets.deploy if self.make_targets.deploy else deploy
        self.make_targets.inject_fault = self.make_targets.inject_fault if self.make_targets.inject_fault else inject_fault
        self.make_targets.evaluate = self.make_targets.evaluate if self.make_targets.evaluate else evaluate
        self.make_targets.delete = self.make_targets.delete if self.make_targets.delete else delete
        self.make_targets.revert = self.make_targets.revert if self.make_targets.revert else revert
        self.make_targets.get = self.make_targets.get if self.make_targets.get else get
        self.make_targets.status = self.make_targets.status if self.make_targets.status else status
        self.make_targets.on_error = self.make_targets.on_error if self.make_targets.on_error else on_error

    def __get_target(self, mkcmd: MakeCmd, default: Optional[str]) -> None:
        if self.make_targets:
            if mkcmd.unused:
                return None
            else:
                return mkcmd.target
        return default

    def get_bundle_status(self):
        mk = self.make_targets.status
        status = self.invoke_bundle(mk.target)
        data = json.loads(status)
        return BundleStatus.model_validate(data["status"])

    def get_bundle(self) -> Dict[str, Any]:  # TODO: define Class instead of dict
        mk = self.make_targets.get
        if mk.unused:
            return {}
        res = self.invoke_bundle(mk.target)
        data = json.loads(res)
        if not "metadata" in data:
            data["metadata"] = {}
        if not "goal" in data["metadata"]:
            data["metadata"]["goal"] = ""
        return data

    def deploy_bundle(self):
        logger = self.logger

        mk = self.make_targets.deploy
        if mk.unused:
            return
        logger.info(f"Deploy bundle '{self.bundle.name}'...")
        self.invoke_bundle(mk.target)

        wait_phase_name = "FaultInjected" if self.make_targets.inject_fault.unused else "Deployed"
        if not self.wait_bundle(wait_phase_name, interval=self.bundle.polling_interval, timeout=self.bundle.bundle_ready_timeout):
            raise BundleError("Deployment Failed", "deploy", mk.target)

    def inject_fault(self):
        logger = self.logger

        mk = self.make_targets.inject_fault
        if mk.unused:
            return
        logger.info(f"Inject compliance violation for '{self.bundle.name}'...")
        self.invoke_bundle(mk.target)
        if not self.wait_bundle("FaultInjected", interval=self.bundle.polling_interval, timeout=self.bundle.bundle_ready_timeout):
            raise BundleError("FaultInjection Failed", "FaultInjected", mk.target)

    def delete_bundle(self, soft_delete=False):
        logger = self.logger

        try:
            if soft_delete:
                logger.info(f"Soft-delete bundle '{self.bundle.name}'...")
                mk = self.make_targets.revert
                phase = "FaultInjected"
                status = "False"
            else:
                logger.info(f"Delete bundle  (remove bundle)'{self.bundle.name}'...")
                mk = self.make_targets.delete
                phase = "Destroyed"
                status = "True"
            if mk.unused:
                return
            self.invoke_bundle(mk.target, max_retry=1)
            if not self.wait_bundle(phase, status=status, interval=self.bundle.polling_interval, timeout=self.bundle.bundle_ready_timeout):
                raise BundleError("Failed to delete", "FaultInjected", self.bundle.make_target_mapping.revert.target)
        except BundleError as e:
            raise e
        except Exception as e:
            logger.error(f"Bundle deletion was not succeeded. Continue to next: {e}")
            logger.error("Continue to next...")

    def get_incident(self) -> bool:
        return not self.get_incident_details().pass_

    def get_incident_details(self) -> BundleEvaluation:
        return self.evaluate()

    def evaluate(self) -> BundleEvaluation:
        mk = self.make_targets.evaluate
        if mk.unused:
            return

        result = self.invoke_bundle(mk.target)
        result = json.loads(result)
        if not "report" in result:
            result["report"] = ""
        if not isinstance(result["report"], str):
            result["report"] = json.dumps(result["report"])
        if "details" in result and not isinstance(result["details"], str):
            result["details"] = json.dumps(result["details"])
        return BundleEvaluation.model_validate(result)

    def error_action(self) -> Optional[str]:
        mk = self.make_targets.on_error
        if not mk or mk.unused:
            message = "No error handler is registered. Nothing to do."
            logger.info(message)
            return
        logger.info(f"Executing 'on_error' target: {mk.target}, {mk.params}, {mk.env}.")
        extra_args = mk.params if mk.params else []
        env = mk.env if mk.env else {}
        try:
            res = self.invoke_bundle(mk.target, extra_args=extra_args, env=env)
            if not self.wait_bundle("Destroyed", interval=self.bundle.polling_interval, timeout=self.bundle.bundle_ready_timeout):
                raise BundleError("ErrorAction Failed", "Destroyed", mk.target)
            return res
        except Exception as e:
            message = f"Failed to execute 'on_error' target: {mk.target}. " f"Exception: {type(e).__name__}, Message: {str(e)}"
            logger.error(message, exc_info=True)
            return message

    def invoke_bundle(self, target, extra_args=[], env={}, retry=0, max_retry=DEFAULT_MAX_RETRY, interval=DEFAULT_RETRY_INTERVAL):
        logger = self.logger

        try:
            current_env = os.environ.copy()
            commant_args = ["make", target, f"SHARED_WORKSPACE={self.bundle_request.shared_workspace}"]
            if self.bundle_request.input_file:
                commant_args.append(f"INPUT_FILE={self.bundle_request.input_file}")
            if self.bundle.params:
                for key, value in self.bundle.params.items():
                    commant_args.append(f"{key}={value}")
            if len(extra_args) > 0:
                commant_args = commant_args + extra_args
            if self.is_test:
                commant_args += ["TEST=true"]
            cwd = self.bundle.get_path().as_posix()
            self.observer.notify("invoke_bundle:run_process:start", {"target": target, "commant_args": commant_args, "cwd": cwd, "env": current_env})
            process = subprocess.Popen(
                commant_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                cwd=cwd,
                env=current_env,
            )

            process.wait()
            returncode = process.returncode
            stdout = process.stdout.read()
            stderr = process.stderr.read()

            self.observer.notify("invoke_bundle:run_process:end", {"returncode": returncode, "stdout": stdout, "stderr": stderr, "retry": retry})

            if returncode != 0:
                logger.error(f"An error occurred. Return code: {returncode}")
                logger.error(stderr)
                _retry = retry + 1
                if _retry > max_retry:
                    raise Exception(f"{_retry} is exxess {max_retry}")
                logger.error(f"Retry {_retry}/{max_retry}")
                time.sleep(interval)
                return self.invoke_bundle(target, extra_args, retry=_retry)
            return stdout

        except Exception as e:
            message = f"An exception occurred: {e}"
            self.observer.notify("invoke_bundle:run_process:error", {"error": message})
            logger.error(message)

    def wait_bundle(self, type, status="True", interval: Optional[int] = None, timeout: Optional[int] = None) -> bool:
        interval = interval if interval else DEFAULT_WAIT_INTERVAL
        timeout = timeout if timeout else DEFAULT_WAIT_TIMEOUT
        logger = self.logger

        bundle_name = self.bundle.name
        start_time = time.time()
        while time.time() - start_time < timeout:
            bundle_status = self.get_bundle_status()
            conditions = [x for x in bundle_status.conditions if x.type == type]
            if len(conditions) > 0:
                condition = conditions[0]
            else:
                logger.error(f"Condition '{type}' is not found for {bundle_name}.")
                return False
            logger.debug(f"Check condition {bundle_name} {type} {status}: {condition}")
            if condition.status == status:
                logger.info(f"Condition '{type}' is satisfied for {bundle_name}.")
                return True
            else:
                if condition.reason in ["DeploymentFailed", "FaultInjectionFailed", "DestroyFailed"]:
                    logger.error(f"Some errors happened on the bundle {bundle_name}. Details: {condition.message}")
                    return False
                if condition.message:
                    logger.info(condition.message)
            time.sleep(interval)
        logger.error(f"Timed out for {bundle_name}.")
        return False

    def wait_for_violation_resolved(self, interval: Optional[int] = None, timeout: Optional[int] = None) -> bool:
        interval = interval if interval else DEFAULT_WAIT_INTERVAL
        timeout = timeout if timeout else DEFAULT_WAIT_TIMEOUT
        logger = self.logger

        def callback(result):
            if not result:
                logger.info(f"The problem is resolved for {self.bundle.name}.")
                return True
            return False

        return self.wait_for_violation(callback, interval=interval, timeout=timeout)

    def wait_for_violation(self, callback, interval: Optional[int] = None, timeout: Optional[int] = None) -> bool:
        interval = interval if interval else DEFAULT_WAIT_INTERVAL
        timeout = timeout if timeout else DEFAULT_WAIT_TIMEOUT
        logger = self.logger

        bundle_name = self.bundle.name
        logger.info(f"Watch a problem for {bundle_name}...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            result = self.get_incident()
            logger.debug(f"The problem {result} for {bundle_name}.")
            if callback(result):
                return True
            time.sleep(interval)
        return False


class BundleError(Exception):

    def __init__(self, message: str, phase: str, make_target: str):
        self.message = message
        self.phase = phase
        self.make_target = make_target
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        return f"Bundle operation at {self.phase} [{self.make_target}] error: {self.message}"
