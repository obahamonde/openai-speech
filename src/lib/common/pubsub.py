"""PubSub engine"""

import os
from typing import AsyncGenerator, Generic, TypeVar, Type
from typing_extensions import ParamSpec, TypedDict, Required
from dataclasses import dataclass

import typing_extensions as tpe
import aioredis
import orjson
from api.lib.utils import get_logger, handle
from openai._utils._proxy import LazyProxy
from aioredis.client import PubSub
from pydantic import BaseModel
from api.lib.utils import get_key

T = TypeVar("T", bound=BaseModel)
P = ParamSpec("P")

logger = get_logger(__name__)


class Message(TypedDict, total=False):
    content: Required[str]
    code: Required[int]


pool = aioredis.Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379"))  # type: ignore


@dataclass
class PubSubChannel(LazyProxy[PubSub], Generic[T]):
    """
    PubSub channel to send function call results to the client.
    """

    pubsub: PubSub
    namespace: str
    data_type: Type[T]

    @tpe.override
    def __init__(self, *, namespace: str, data_type: Type[T]):
        self.namespace = namespace
        self.data_type = data_type
        self.pubsub = self.__load__()

    def __load__(self):
        """
        Lazy loading of the PubSub object.
        """
        return pool.pubsub()  # type: ignore

    @handle
    async def sub(self) -> AsyncGenerator[T, None]:
        """
        Subscribes to the PubSub channel and yields messages as they come in.
        """
        await self.pubsub.subscribe(self.namespace)  # type: ignore
        logger.info("Subscribed to %s", self.namespace)
        async for message in self.pubsub.listen():  # type: ignore
            try:
                data = get_key(object=message, key="data")  # type: ignore
                if data is None:
                    continue
                logger.info("Received message %s", data)
                yield self.data_type.model_validate_json(orjson.dumps(data))  # type: ignore
            except (KeyError, AssertionError, UnicodeDecodeError, AttributeError):
                continue

    @handle
    async def _send(self, *, data: str) -> None:
        """
        Protected method to send a message to the PubSub channel.
        """
        await pool.publish(self.namespace, data)  # type: ignore
        logger.info("Message published to %s", self.namespace)

    @handle
    async def pub(self, *, data: T):
        """
        Public method to send a function call result to the PubSub channel.
        """
        await self._send(data=data.model_dump_json())
        return Message(content="OK", code=200)
