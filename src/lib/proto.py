import typing as tp
from typing_extensions import ParamSpec, Protocol
from pydantic import BaseModel
from .lib import Tool

# Type variables
T = tp.TypeVar("T")
T_co = tp.TypeVar("T_co", covariant=True)
T_con = tp.TypeVar("T_con", contravariant=True)
M_co = tp.TypeVar("M_co", covariant=True)
M_con = tp.TypeVar("M_con", bound=BaseModel, contravariant=True)
P = ParamSpec("P")


# GenerationResponse class
class GenerationResponse(Tool, tp.Generic[T_co]):
    model_config = {"extra": "allow", "arbitrary_types_allowed": True}
    created: int
    data: tp.Iterable[T_co]


# RepositoryProtocol interface
class RepositoryProtocol(tp.Generic[T_con, M_co], Protocol):
    async def create(self, *, params: T_con) -> M_co: ...
    async def retrieve(self, *, id: str) -> M_co: ...
    async def update(self, *, params: T_con) -> M_co: ...
    async def delete(self, *, id: str) -> None: ...
    async def list(
        self,
        /,
        *,
        after: str | None,
        limit: int | None,
    ) -> tp.AsyncIterator[M_co] | tp.Iterator[M_co]: ...


# GenerativeProtocol interface
class GenerativeProtocol(tp.Generic[T_con, T_co], Protocol):
    async def generate(
        self, *, params: T_con
    ) -> tp.Union[GenerationResponse[T_co], tp.AsyncIterator[T_co]]: ...
