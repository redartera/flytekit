import json
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import cloudpickle

from flytekit import FlyteContextManager, lazy_module
from flytekit.core.type_engine import TypeEngine
from flytekit.extend.backend.base_agent import (
    AgentRegistry,
    AsyncAgentBase,
    Connection,
    Resource,
    ResourceMeta,
)
from flytekit.extend.backend.utils import convert_to_flyte_phase, get_agent_secret
from flytekit.models.literals import LiteralMap
from flytekit.models.task import TaskTemplate

openai = lazy_module("openai")
OPENAI_API_KEY = "FLYTE_OPENAI_API_KEY"


class State(Enum):
    Running = ["in_progress", "finalizing", "validating"]
    Success = ["completed"]
    Failed = ["failed", "cancelled", "cancelling", "expired"]

    @classmethod
    def key_by_value(cls, value):
        for member in cls:
            if value in member.value:
                return member.name


@dataclass
class BatchEndpointConnection(Connection):
    openai_api_key: str


@dataclass
class BatchEndpointMetadata(ResourceMeta):
    openai_org: str
    batch_id: str

    def encode(self) -> bytes:
        return cloudpickle.dumps(self)

    @classmethod
    def decode(cls, data: bytes) -> "BatchEndpointMetadata":
        return cloudpickle.loads(data)


class BatchEndpointAgent(AsyncAgentBase):
    name = "OpenAI Batch Endpoint Agent"

    def __init__(self):
        super().__init__(
            task_type_name="openai-batch-endpoint",
            metadata_type=BatchEndpointMetadata,
            connection_type=BatchEndpointConnection,
        )

    async def create(
        self,
        task_template: TaskTemplate,
        inputs: Optional[LiteralMap] = None,
        connection: Optional[BatchEndpointConnection] = None,
        **kwargs,
    ) -> BatchEndpointMetadata:
        ctx = FlyteContextManager.current_context()
        input_values = TypeEngine.literal_map_to_kwargs(
            ctx,
            inputs,
            {"input_file_id": str},
        )
        custom = task_template.custom

        async_client = openai.AsyncOpenAI(
            organization=custom.get("openai_organization"),
            api_key=connection.openai_api_key or get_agent_secret(secret_key=OPENAI_API_KEY),
        )

        custom["config"].setdefault("completion_window", "24h")
        custom["config"].setdefault("endpoint", "/v1/chat/completions")

        result = await async_client.batches.create(
            **custom["config"],
            input_file_id=input_values["input_file_id"],
        )
        batch_id = result.id

        return BatchEndpointMetadata(batch_id=batch_id, openai_org=custom["openai_organization"])

    async def get(
        self,
        resource_meta: BatchEndpointMetadata,
        connection: Optional[BatchEndpointConnection] = None,
        **kwargs,
    ) -> Resource:
        async_client = openai.AsyncOpenAI(
            organization=resource_meta.openai_org,
            api_key=connection.openai_api_key or get_agent_secret(secret_key=OPENAI_API_KEY),
        )

        retrieved_result = await async_client.batches.retrieve(resource_meta.batch_id)
        current_state = retrieved_result.status

        flyte_phase = convert_to_flyte_phase(State.key_by_value(current_state))

        message = None
        if current_state in State.Failed.value and retrieved_result.errors:
            data = retrieved_result.errors.get("data")
            if data and data[0].get("message"):
                message = data[0]["message"]

        result = None
        if current_state in State.Success.value:
            result = {"result": json.dumps(retrieved_result)}

        return Resource(phase=flyte_phase, outputs=result, message=message)

    async def delete(
        self,
        resource_meta: BatchEndpointMetadata,
        connection: Optional[BatchEndpointConnection] = None,
        **kwargs,
    ):
        async_client = openai.AsyncOpenAI(
            organization=resource_meta.openai_org,
            api_key=connection.openai_api_key or get_agent_secret(secret_key=OPENAI_API_KEY),
        )

        await async_client.batches.cancel(resource_meta.batch_id)


AgentRegistry.register(BatchEndpointAgent())