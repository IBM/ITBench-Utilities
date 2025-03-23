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

from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field

from itbench_utilities.app.models.base import Env


class AgentRunCommand(BaseModel):
    command: Optional[List[str]] = Field(None, description="The list of command strings to execute (entrypoint).")
    args: Optional[List[str]] = Field(None, description="The list of arguments to pass to the command.")
    env: Optional[List[Env]] = Field(None, description="A list of environment variables to be passed to the container.")


class AgentInfo(BaseModel):
    id: str = Field(..., description="Unique Identifier")
    name: str = Field(..., description="The name of Agent.")
    directory: str = Field(..., description="The directory path of the Agent.")
    description: Optional[str] = Field(None, description="The description of the Agent.")
    mode: Optional[str] = Field(None, description="If Agent is owned and managed by Benchmark, select Local. Else, Remote. Default Local.")
    run: Optional[AgentRunCommand] = Field(None, description="Command to invoke agent")

    def get_path(self) -> Path:
        return Path(self.directory)
