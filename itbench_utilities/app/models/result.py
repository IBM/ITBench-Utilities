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

from typing import List, Optional

from pydantic import BaseModel

from itbench_utilities.app.models.base import Metadata, Status
from itbench_utilities.models.bundle import BundleResult


class ResultSpec(BundleResult):
    bundle_id: str


class Result(BaseModel):
    metadata: Metadata
    spec: ResultSpec
    status: Optional[Status] = None