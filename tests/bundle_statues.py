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
from typing import List, Optional, Tuple

from itbench_utilities.models.bundle import BundleCondition, BundleStatus


def build(type_status_reason_trios: List[Tuple[str, str, Optional[str]]], current: Optional[BundleStatus] = None) -> BundleStatus:
    kubeconfig = "TBD"
    basetime = datetime(year=2024, month=10, day=1, hour=0, minute=0, second=0)
    conditions = [BundleCondition(lastTransitionTime=basetime, type=x[0], status=x[1], reason=x[2]) for x in type_status_reason_trios]

    if current:
        new_conditions = []
        for condition in current.conditions:
            new_conditions.append(condition)

        for condition in conditions:
            founds = [x for x in enumerate(current.conditions) if x[1].type == condition.type]
            if len(founds) > 0:
                idx = founds[0][0]
                new_conditions[idx] = condition
    else:
        new_conditions = conditions
    return BundleStatus(kubeconfig=kubeconfig, conditions=new_conditions)


INITIAL = build(
    [
        ("Deployed", "False", None),
        ("FaultInjected", "False", None),
        ("Destroyed", "False", None),
    ]
)
DEPLOYING = build([], INITIAL)
DEPLOYED = build(
    [
        ("Deployed", "True", None),
    ],
    DEPLOYING,
)
FAULT_INJECTING = build([], DEPLOYED)
FAULT_INJECTED = build(
    [
        ("FaultInjected", "True", None),
    ],
    FAULT_INJECTING,
)
DESTROYING = build([], FAULT_INJECTED)
DESTROYED = build(
    [
        ("Destroyed", "True", None),
    ],
    FAULT_INJECTED,
)
