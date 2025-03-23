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

import os
from typing import List, Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEFAULT_MINIBENCH_HOST = "127.0.0.1"
DEFAULT_MINIBENCH_PORT = 8001
DEFAULT_MINIBENCH_TIMEOUT_SECONDS = 600

SERVICE_API_KEY = os.getenv("SERVICE_API_KEY", "")

PROJECT_LOG_LEVEL = os.getenv("PROJECT_LOG_LEVEL", "")
ROOT_LOG_LEVEL = os.getenv("ROOT_LOG_LEVEL", "")


def get_service_api_key(service_name):
    return SERVICE_API_KEY


class ServiceAccount(BaseModel):
    id: str
    type: str


class AppConfig(BaseSettings):
    host: Optional[str] = Field(DEFAULT_HOST, description="Host to bind the server. Default is 127.0.0.1.")
    port: Optional[int] = Field(DEFAULT_PORT, description="Port to bind the server. Default is 8000.")
    enable_soft_delete: Optional[bool] = Field(False, description="Specifies whether to enable soft-delete (invoke Make revert).")
    service_accounts: Optional[List[ServiceAccount]] = None
    ssl_enabled: Optional[bool] = Field(False, description="Enable or disable SSL. Set to True to enable SSL for the server.")
    ssl_verify: Optional[bool] = Field(
        False,
        description="Enable or disable SSL certificate verification. Set to True to verify the certificate, or False to disable verification (default: False).",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        env_prefix = "IT_BENCH_"
