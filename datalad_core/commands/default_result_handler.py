from collections.abc import Generator
from inspect import Parameter
from types import MappingProxyType
from typing import (
    Any,
    Callable,
)

from datalad_core.commands.result_handler import ResultHandler


class ResultError(RuntimeError):
    """Exception raise when error results have been observed"""

    def __init__(self, failed=None, msg=None):
        super().__init__(msg)
        self.failed = failed


class StandardResultHandler(ResultHandler):
    """Result handler commonly used by commands

    .. note::

       This is largely a no-op implementation for now. It will be co-developed
       with actual commands.

    Command must return an iterable (typically a generator) of
    result instances.
    """

    @classmethod
    def get_extra_kwargs(cls) -> MappingProxyType[str, Parameter]:
        kwargs = {
            'on_failure': Parameter(
                name='on_failure',
                kind=Parameter.KEYWORD_ONLY,
                default='continue',
                annotation=str,
            ),
        }
        return MappingProxyType(kwargs)

    def __call__(self, producer: Callable):
        """ """
        # book-keeping whether to raise an exception
        error_results: list[dict] = []
        on_failure = self._cmd_kwargs['on_failure']

        for res in producer():
            if not res or 'action' not in res:
                continue

            self.log_result(res)
            self.render_result(res)

            if on_failure in ('continue', 'stop') and res['status'] in (
                'impossible',
                'error',
            ):
                error_results.append(res)
                if on_failure == 'stop':
                    # first fail -> that's it
                    # raise will happen after the loop
                    break

            # TODO: implement result filtering
            # if not self.keep_result(res):
            #     continue

            yield from self.transform_result(res)

        # TODO: implement result summary rendering
        # self.render_result_summary()

        if error_results:
            msg = 'Command did not complete successfully'
            raise ResultError(failed=error_results, msg=msg)

    def log_result(self, result: dict) -> None:
        """ """

    # TODO: implement result summary rendering
    # def want_custom_result_summary(self, mode: str) -> bool:
    #     """ """
    #     return False

    def render_result(self, result: dict) -> None:
        """ """

    # TODO: implement result summary rendering
    # def render_result_summary(self) -> None:
    #     """ """

    def transform_result(self, res) -> Generator[Any, None, None]:
        """ """
        yield res

    # TODO: implement result filtering
    # def keep_result(self, res) -> bool:
    #     """ """
    #     return True


__the_default_result_handler_class: type[ResultHandler] = StandardResultHandler


def set_default_result_handler(handler_cls: type[ResultHandler]):
    """Set a default result handler class for use by ``@datalad_command``

    This must be a class implementing the :class:`ResultHandler` interface.
    """
    global __the_default_result_handler_class  # noqa: PLW0603
    __the_default_result_handler_class = handler_cls


def get_default_result_handler() -> type[ResultHandler]:
    """Get the default result handler class used by ``@datalad_command``

    See :func:`set_default_result_handler` for more information.
    """
    return __the_default_result_handler_class
