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

from pydantic import BaseModel, Field, model_validator

from itbench_utilities.app.models.base import Env, Metadata, Status


class MakeCmd(BaseModel):
    target: Optional[str] = Field(None, description="The Makefile target name.")
    env: Optional[List[Env]] = Field(None, description="A list of environment variables to be passed to the scenario.")
    params: Optional[Dict[str, str]] = Field(None, description="Paramaters to be passed to Make invocation.")
    unused: Optional[bool] = Field(False, description="Set true if not used this make target.")

    @model_validator(mode="after")
    def validate_target(cls, values):
        """Validate that `target` is required if `unused` is False or not set."""
        if not values.unused and not values.target:
            raise ValueError("The 'target' field is required when 'unused' is False or not set.")
        return values


class MakeTargetMapping(BaseModel):
    deploy: MakeCmd = Field(..., description="The Makefile target for deploying bundle.")
    inject_fault: MakeCmd = Field(..., description="The Makefile target for performing fault injection.")
    evaluate: MakeCmd = Field(..., description="The Makefile target for evaluating results.")
    delete: MakeCmd = Field(..., description="The Makefile target for deleting bundle.")
    revert: Optional[MakeCmd] = Field(None, description="The Makefile target for reverting environment without deleting.")
    status: MakeCmd = Field(..., description="The Makefile target for retrieving or polling status.")
    get: MakeCmd = Field(..., description="The Makefile target for retrieving data.")
    on_error: Optional[MakeCmd] = Field(
        None, description="The Makefile target to be executed on error. If not provided, no action will be taken on error."
    )


class BundleSpec(BaseModel):
    name: str
    path: Optional[str] = Field(None, description="The directory path where the scenario's Makefile is located.")
    root_dir: Optional[str] = Field("", description="The base directory used to resolve the full path as root_dir/path.")
    scenario_type: Optional[str] = Field(None, description="The type or category of the scenario.")
    description: Optional[str] = Field(None, description="A brief explanation or summary of the scenario.")
    version: Optional[str] = Field("latest")
    bundle_ready_timeout: Optional[int] = Field(
        300, description="Maximum time in seconds to wait for the scenario to become ready and an agent to be assigned."
    )
    agent_operation_timeout: Optional[int] = Field(
        300, description="Maximum time in seconds to wait for the agent to complete the operation after being assigned."
    )
    env: Optional[List[Env]] = Field(None, description="A list of environment variables to be passed to the scenario.")
    params: Optional[Dict[str, str]] = Field(None, description="Paramaters to be passed to Make invocation.")
    data: Optional[Dict[str, Any]] = Field(
        None,
        description="A dictionary to hold various data related to the scenario, such as input parameters, configuration details, or outputs generated during execution.",
    )
    assigned_agent_id: Optional[str] = Field(
        None, description="ID of the agent assigned to manage this bundle. This will be set by Benchmark Service during benchmarking"
    )
    make_target_mapping: Optional[MakeTargetMapping] = Field(
        None, description="A mapping of each bundle phase's action to their corresponding Makefile command configurations."
    )
    enable_evaluation_wait: Optional[bool] = Field(False, description="Specifies whether to enable a waiting period for evaluation.")


class Bundle(BaseModel):
    metadata: Metadata
    spec: BundleSpec
    status: Optional[Status] = None
