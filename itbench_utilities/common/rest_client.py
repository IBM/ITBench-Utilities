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
from typing import Any, Dict, Optional

import requests
import urllib3
from urllib3.exceptions import InsecureRequestWarning

from itbench_utilities.app.models.base import AgentPhaseEnum
from itbench_utilities.app.utils import create_status

urllib3.disable_warnings(InsecureRequestWarning)

logger = logging.getLogger(__name__)


class RestClient:
    def __init__(
        self,
        host: str,
        port: int,
        headers: Optional[Dict[str, str]] = None,
        ssl: Optional[bool] = False,
        verify: Optional[bool] = False,
        root_path: Optional[str] = "",
    ):
        protocol = "https" if ssl else "http"
        self.base_url = f"{protocol}://{host}:{port}{root_path}" if port > 0 else f"{protocol}://{host}{root_path}"
        self.headers = headers
        if self.headers:
            self.headers["Content-type"] = "application/json"
        else:
            self.headers = {"Content-type": "application/json"}
        self.verify = verify if verify else False

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        _endpoint = endpoint.lstrip("/")
        url = f"{self.base_url}/{_endpoint}"
        response = requests.get(url, headers=self.headers, params=params, verify=self.verify)
        response.raise_for_status()
        return response

    def assign(self, benchmark_id: str, agent_id: str, bundle_id: str) -> requests.Response:
        url = f"{self.base_url}/benchmarks/{benchmark_id}/assign_agent"
        response = requests.put(url, headers=self.headers, json={"agent_id": agent_id, "bundle_id": bundle_id}, verify=self.verify)
        return response

    def put(self, endpoint: str, body = None, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        _endpoint = endpoint.lstrip("/")
        url = f"{self.base_url}/{_endpoint}"
        response = requests.put(
            url,
            headers=self.headers,
            data=body,
            params=params,
            verify=self.verify,
        )
        return response

    def post(self, endpoint: str, body = None, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        _endpoint = endpoint.lstrip("/")
        url = f"{self.base_url}/{_endpoint}"
        response = requests.post(
            url,
            headers=self.headers,
            data=body,
            params=params,
            verify=self.verify,
        )
        return response

    def push_agent_status(self, benchmark_id: str, agent_id: str, phase: AgentPhaseEnum, message: Optional[str] = None):
        url = f"{self.base_url}/benchmarks/{benchmark_id}/agents/{agent_id}/status"
        status = create_status(phase.value, message)
        requests.put(url, headers=self.headers, data=status.model_dump_json(), verify=self.verify)

    def upload_file(self, benchmark_id: str, file_path: str, new_file_name: str):
        with open(file_path, "rb") as file:
            files = {"file": (new_file_name, file)}
            url = f"{self.base_url}/benchmarks/{benchmark_id}/file"
            response = requests.post(url, headers={"Authorization": self.headers["Authorization"]}, files=files, verify=self.verify)
            response.raise_for_status()

    def login(self, username, password):
        url = f"{self.base_url}/token"
        response = requests.post(url, data={"username": username, "password": password}, verify=self.verify)
        token = response.json()["access_token"]
        self.headers["Authorization"] = f"Bearer {token}"
