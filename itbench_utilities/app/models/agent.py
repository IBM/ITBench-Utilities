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

from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from itbench_utilities.app.models.base import Env, Metadata, Status
from itbench_utilities.app.models.agent_type_definition import AgentTypeTask


class AgentAccessInfo(BaseModel):
    id: str
    name: str
    source_id: str
    status_endpoint: str


class BundleAccessInfo(BaseModel):
    id: str
    name: str
    source_id: str
    status_endpoint: str
    manifest_endpoint: str


class AgentBenchmarkEntry(BaseModel):
    benchmark_id: str
    agent_access_info: AgentAccessInfo
    bundle_access_infos: List[BundleAccessInfo]
    status: Status


class AgentManifest(BaseModel):
    token: Optional[str] = ""
    manifest_endpoint: Optional[str] = None
    benchmark_entries: List[AgentBenchmarkEntry] = []


class AgentExpectedApiResponse(BaseModel):
    task_list: List[AgentTypeTask] = []
    sample_api_response: Dict[str, Any] = {}
    sample_url: str
    sample_cli: str


class AgentSpec(BaseModel):
    name: str
    type: Optional[str] = None
    level: Optional[str] = None
    scenario_categories: Optional[List[str]] = []
    expected_api_response: Optional[AgentExpectedApiResponse] = None
    path: Optional[str] = None
    mode: Optional[str] = "remote"
    env: Optional[List[Env]] = None
    user_id: Optional[str] = None
    agent_manifest: Optional[AgentManifest] = None


class Agent(BaseModel):
    metadata: Metadata
    spec: AgentSpec
    status: Optional[Status] = None
