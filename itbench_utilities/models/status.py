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

from pydantic import BaseModel, Field


class Condition(BaseModel):
    lastTransitionTime: datetime = Field(..., description="The last time the condition transitioned from one status to another.")
    status: str = Field(..., description='The status of the condition: "True", "False", or "Unknown".')
    type: str = Field(..., description="The type of condition (e.g., 'Deployed', 'FaultInjected', 'Destroyed').")
    message: Optional[str] = Field(default=None, description="A human-readable message indicating details about the condition.")
    reason: Optional[str] = Field(default=None, description="A brief machine-readable explanation for the condition's status.")


class Status(BaseModel):
    conditions: List[Condition] = Field(..., description="List of conditions for the bundle.")
