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
from typing import Optional
from uuid import uuid4

from itbench_utilities.app.models.base import Status


def get_tempdir(id: str):
    return f"/tmp/{id}"


def get_timestamp() -> datetime:
    return datetime.now(timezone.utc)


def get_timestamp_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def get_uuid() -> str:
    return str(uuid4())


def create_status(phase: str, message: Optional[str] = None) -> Status:
    return Status(lastTransitionTime=get_timestamp(), phase=phase, message=message)
