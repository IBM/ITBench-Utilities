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

import logging
from datetime import timedelta
from typing import List

from itbench_utilities.models.benchmark import BenchmarkResult
from itbench_utilities.models.bundle import BundleResult

logger = logging.getLogger(__name__)
log_format = "[%(asctime)s %(levelname)s %(name)s] %(message)s"


class Analyzer:

    def __init__(self, bundle_results: List[BundleResult]) -> None:
        self.df = BundleResult.to_dataframe(bundle_results)
        self.bundle_results = bundle_results

    def calc_mttr(self) -> timedelta:
        return self.df[BundleResult.Column.ttr].mean().to_pytimedelta()

    def calc_num_of_pass(self) -> float:
        return self.df[BundleResult.Column.passed].sum().item()

    def calc_pass_rate(self) -> float:
        total = len(self.df[self.df[BundleResult.Column.errored] == False])
        if total == 0:
            return 0
        return self.calc_num_of_pass() / total

    def to_benchmark_result(self, title, agent) -> BenchmarkResult:
        mttr = self.calc_mttr()
        num_of_pass = self.calc_num_of_pass()
        score = self.calc_pass_rate()
        incident_types = self.df[BundleResult.Column.incident_type].dropna().unique()
        latest_one = max(self.bundle_results, key=lambda x: x.date)
        return BenchmarkResult(
            name=title,
            agent=agent,
            incident_type=",".join(incident_types),
            mttr=mttr,
            num_of_passed=num_of_pass,
            score=score,
            results=self.bundle_results,
            date=latest_one.date,
        )
