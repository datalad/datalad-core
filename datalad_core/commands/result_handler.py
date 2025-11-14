from __future__ import annotations

from abc import (
    ABC,
    abstractmethod,
)
from types import MappingProxyType
from typing import (
    TYPE_CHECKING,
    Any,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from inspect import Parameter


class ResultHandler(ABC):
    """Abstract base class for result handlers

    Any subclass must implement ``__call__``. This method will be executed
    with a callable as the only argument. The callable is fully parameterized
    and takes no parameters. The ``__call__`` implementation must run this
    callable to trigger execution and receive and post-process results
    in whatever fashion.
    """

    def __init__(
        self,
        cmd_kwargs,
    ):
        self._cmd_kwargs = cmd_kwargs

    @classmethod
    def get_extra_kwargs(cls) -> MappingProxyType[str, Parameter]:
        """Returns a mapping with specifications of extra command parameters"""
        return MappingProxyType({})

    @abstractmethod
    def __call__(self, producer: Callable) -> Any:
        """Implement to run commands and post-process return values"""


class PassthroughHandler(ResultHandler):
    """Minimal handler that relays any return value unmodified

    This handler reports no extra keyword arguments via its
    :meth:`get_extra_kwargs`.
    """

    def __call__(self, producer: Callable) -> Any:
        return producer()
