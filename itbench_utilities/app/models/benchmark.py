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
from typing import List, Optional

from pydantic import BaseModel

from itbench_utilities.app.models.agent import AgentManifest
from itbench_utilities.app.models.base import Metadata, Status
from itbench_utilities.app.models.scenario import Scenario


class BenchmarkSpec(BaseModel):
    name: str
    runner_id: Optional[str] = None
    agent_id: Optional[str] = None
    scenarios: Optional[List[Scenario]] = None
    log_file_path: Optional[str] = None
    bundle_results_path: Optional[str] = None


class Benchmark(BaseModel):
    metadata: Metadata
    spec: BenchmarkSpec
    status: Optional[Status] = None


class AgentAssignment(BaseModel):
    bundle_id: str
    agent_id: str


class AgentStatus(Status):
    id: str
    name: str
    current_assignment: str


class BundleStatus(Status):
    id: str
    name: str
    assigned_agent_id: str


class BenchmarkStatus(BaseModel):
    id: str
    name: str
    creation_timestamp: datetime
    agent: AgentStatus
    bundles: List[BundleStatus]


class BenchmarkJobTake(BaseModel):
    runner_id: str


class BenchmarkJob(BaseModel):
    benchmark: Benchmark
    agent_manifest: Optional[AgentManifest] = None
