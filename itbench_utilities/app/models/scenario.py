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

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from itbench_utilities.app.models.base import Metadata, Status
from itbench_utilities.app.models.bundle import BundleSpec


class ScenarioSpec(BaseModel):
    type: str = Field(..., description="The Agent type, e.g., 'SRE', 'FinOps', 'CISO'.")
    name: str = Field(..., description="The name of the scenario, providing a human-readable identifier.")
    description: str = Field(..., description="A brief explanation of what the scenario entails.")
    complexity: str = Field(..., description="The complexity level of the scenario, e.g., 'Low', 'Medium', or 'High'.")
    category: str = Field(..., description="The category of the scenario, e.g., 'resource unavailability', 'saturation', 'traffic' for SRE.")
    scenario_class: Optional[str] = Field(
        None, alias="class", description="The class or classification of the scenario, e.g. 'rhel9 CIS', 'kubernetes CIS'."
    )
    instance_id: str = Field(..., description="A unique identifier for the specific instance (bundle id) of the scenario.")
    model_config = ConfigDict(populate_by_name=True)


class Scenario(BaseModel):
    metadata: Metadata
    spec: ScenarioSpec
    status: Optional[Status] = None


class ScenarioBundlePair(BaseModel):
    bundle: BundleSpec
    scenario: ScenarioSpec
