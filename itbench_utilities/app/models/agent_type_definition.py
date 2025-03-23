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

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class AgentTypeTask(BaseModel):
    name: str = Field(..., description="Task name, e.g. generate_assessment")
    description: str = Field(..., description="Task description, e.g., Time to Generate Assessment Posture (seconds)")


class AgentTypeDefinition(BaseModel):
    id: str = Field(..., description="The human readable unique identifier for the Agent type, e.g., 'SRE' or 'CISO'.")
    allowed_levels: List[str] = Field(
        ..., description="A list of levels permitted for this Agent type, such as 'Beginner', 'Intermediate', or 'Expert'."
    )
    allowed_categories: List[str] = Field(
        ...,
        description="A list of scenario categories applicable to this Agent type, such as 'resource unavailability', 'saturation', or 'traffic' for SRE.",
    )
    allowed_complexities: List[str] = Field(
        ..., description="A list of scenario complexity levels suitable for this Agent type, such as 'Low', 'Medium', or 'High'."
    )
    level_to_complexities_map: Dict[str, List[str]] = Field(
        ..., description="A mapping of Agent levels to the corresponding scenario complexity levels."
    )
    tasks: List[AgentTypeTask] = Field(..., description="A list of Agent task definition")
    sampling_number: int = Field(..., description="The maximum number of sampled scenarios")
