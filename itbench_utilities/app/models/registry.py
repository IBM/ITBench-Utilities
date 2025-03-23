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

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel

from itbench_utilities.app.models.agent import (
    Agent,
    AgentAccessInfo,
    BundleAccessInfo,
)
from itbench_utilities.app.models.base import Status
from itbench_utilities.app.models.benchmark import Benchmark
from itbench_utilities.app.models.bundle import Bundle
from itbench_utilities.app.models.result import Result
from itbench_utilities.app.models.scenario import Scenario


class User(BaseModel):
    username: str
    id: str


class RegistryRequest(BaseModel):
    username: str
    user_id: str


class RegistryItem(BaseModel):
    name: str
    creation_timestamp: datetime
    bundles: List[Bundle] = []
    agents: List[Agent] = []
    scenarios: List[Scenario] = []


class BenchmarkRequest(BaseModel):
    name: str
    agent_id: str
    bundle_ids: Optional[List[str]] = None
    scenario_ids: Optional[List[str]] = None


class DataForAgentRegistration(BaseModel):
    available_types: List[str] = []
    type_to_avalable_levels: Dict[str, List[str]] = None
    type_to_avalable_categories: Dict[str, List[str]] = None


class CreateBenchmarkRequest(BaseModel):
    name: str
    agent_id: str
    immediate: Optional[bool] = False


class BenchmarkInfo(BaseModel):
    id: str
    name: str
    token: str
    result_endpoint: str
    agent_access: Optional[AgentAccessInfo] = None
    bundle_accesses: Optional[List[BundleAccessInfo]] = None
    agents: Optional[List[Agent]] = None
    scenarios: Optional[List[Scenario]] = None
    bundles: Optional[List[Bundle]] = None
    root_benchmark_id: Optional[str] = None
    root_agents: Optional[List[Agent]] = None
    root_bundles: Optional[List[Bundle]] = None
    status: Optional[Status] = None
    creation_timestamp: Optional[datetime] = None


class BenchmarkResultsPair(BaseModel):
    benchmark: Benchmark
    results: List[Result]