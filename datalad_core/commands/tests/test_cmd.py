from inspect import Parameter, signature
from types import MappingProxyType

import pytest

from datalad_core.commands.decorator import datalad_command
from datalad_core.commands.default_result_handler import (
    ResultError,
    get_default_result_handler,
    set_default_result_handler,
)
from datalad_core.commands.result_handler import (
    PassthroughHandler,
    ResultHandler,
)


def test_testcmd_minimal():
    # test thinnest possible wrapper -- no result processing whatsoever,
    # just pass-through.
    # this can be useful, when only parameter validation is desired
    magic_value = 5

    @datalad_command(postproc_cls=PassthroughHandler)
    def test_command():
        """EXPLAIN IT ALL"""
        return magic_value

    assert test_command() == magic_value
    assert 'EXPLAIN IT ALL' in test_command.__doc__


def test_testcmd_plain():
    class TestResultHandler(ResultHandler):
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

        def __call__(self, get_results):
            return list(get_results())

    @datalad_command(
        postproc_cls=TestResultHandler,
    )
    def test_command(
        parg1,
        parg2,  # noqa: ARG001
        *,
        kwarg1=None,  # noqa: ARG001
        kwarg2=True,  # noqa: ARG001
    ):
        yield parg1

    # common args are registered in the signature
    assert 'on_failure' in str(signature(test_command))
    # decorator args are attached to function as attributes
    assert test_command.preproc is None
    assert test_command.extra_kwargs_defaults == {}
    assert test_command.postproc_cls is TestResultHandler

    with pytest.raises(TypeError, match='missing.*required.*parg1.*parg2'):
        test_command()
    test_command('some_parg1', 'some_parg2')


def test_testcmd_default_result_handler_on_failure():
    test_results = [
        {'action': 'test', 'status': 'ok'},
        {'action': 'test', 'status': 'notneeded'},
        {'action': 'test', 'status': 'impossible'},
        {'action': 'test', 'status': 'error'},
    ]
    success = [tr for tr in test_results if tr['status'] in ('ok', 'notneeded')]
    failed = [tr for tr in test_results if tr['status'] in ('impossible', 'error')]

    @datalad_command()
    def test_command():
        yield
        yield from test_results

    assert (
        test_command.postproc_cls.get_extra_kwargs()['on_failure'].default == 'continue'
    )

    res = []
    # we need to have a for-loop here to get as many results out
    # as possible before the exception kicks in
    with pytest.raises(ResultError) as e:  # noqa: PT012
        # `yield None` is ignored
        for r in test_command():
            res.append(r)  # noqa: PERF402

    # all results are yielded, also the error ones
    assert res == test_results
    # the error ones are collected and attached to the exception
    assert e.value.failed == failed

    res = []
    with pytest.raises(ResultError) as e:  # noqa: PT012
        # `yield None` is ignored
        for r in test_command(on_failure='stop'):
            res.append(r)

    # only success results are yielded this time
    assert res == success
    # stopped on first error, hence only one error communicated
    assert e.value.failed == failed[:1]

    assert list(test_command(on_failure='ignore')) == test_results


def test_default_handler_set():
    dhdlr = get_default_result_handler()
    try:
        test_handler_cls = PassthroughHandler
        set_default_result_handler(test_handler_cls)
        assert get_default_result_handler() is test_handler_cls
    finally:
        # restore
        set_default_result_handler(dhdlr)
