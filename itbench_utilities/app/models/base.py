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

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional, TypeVar

from pydantic import BaseModel, Field


class BenchmarkPhaseEnum(str, Enum):
    NotRegistered = "NotRegistered"
    NotStarted = "NotStarted"
    Running = "Running"
    Finished = "Finished"
    PendingResultUpload = "PendingResultUpload"
    Queued = "Queued"
    Error = "Error"


class BundlePhaseEnum(str, Enum):
    NotStarted = "NotStarted"
    Provisioning = "Provisioning"
    Provisioned = "Provisioned"
    FaultInjecting = "FaultInjecting"
    FaultInjected = "FaultInjected"
    Ready = "Ready"
    Evaluating = "Evaluating"
    Evaluated = "Evaluated"
    Terminating = "Terminating"
    Terminated = "Terminated"
    Error = "Error"


class AgentPhaseEnum(str, Enum):
    NotStarted = "NotStarted"
    Initializing = "Initializing"
    Ready = "Ready"
    Executing = "Executing"
    Finished = "Finished"
    Error = "Error"
    TimeedOut = "TimedOut"
    Terminating = "Terminating"
    Terminated = "Terminated"


class Metadata(BaseModel):
    id: str
    resource_type: str
    creation_timestamp: datetime
    labels: Optional[Dict[str, str]] = None
    user_id: Optional[str] = None


class Env(BaseModel):
    name: str
    value: str


def get_timestamp():
    return datetime.now(timezone.utc)


class Status(BaseModel):
    lastTransitionTime: Optional[datetime] = Field(
        default_factory=get_timestamp, description="The last time the condition transitioned from one status to another."
    )
    phase: str = Field(..., description="The phase of the condition.")
    message: Optional[str] = Field(default=None, description="A human-readable message indicating details about the condition.")


class Identifiable(BaseModel):
    metadata: Metadata


T = TypeVar("T", bound=Identifiable)
