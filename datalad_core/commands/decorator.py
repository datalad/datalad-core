from __future__ import annotations

from functools import (
    partial,
    wraps,
)
from inspect import (
    Parameter,
    signature,
)
from typing import (
    TYPE_CHECKING,
    Any,
)

from datalad_core.commands.default_result_handler import get_default_result_handler

if TYPE_CHECKING:
    from datalad_core.commands.preproc import ParamProcessor
    from datalad_core.commands.result_handler import ResultHandler


# this could be a function decorator, but we use a class, because
# it is less confusing to read (compared to the alternative decorator
# factory
class datalad_command:  # noqa: N801  MIH wants lower-case
    """Wrap a callable with parameter preprocessing and result post-processing

    This decorator can handle a wide range of callables. However, they must not
    have any positional-only parameters.

    Before a wrapped callable is executed, an optional parameter preprocessor
    ``preproc`` is applied. Any implementation that matches the
    :class:`ParamProcessor` interface can be used, and arbitrary preprocessing
    steps, like type-coercion or validation can be performed.

    The return value of the wrapped callable is post-processed with an instance
    of the class returned by :func:`get_default_result_handler`, or that given
    as ``postproc_cls`` parameter of the decorator. Any implementation
    of the :class:`ResultHandler` interface can be used to apply arbitrary
    return value post-processing. An instance of the given result handler class
    is created, and the full parameterization is passed to the constructor
    as an argument, such that a result handler can inspect and tune itself,
    based on a concrete parameterization.

    If a given :class:`ResultHandler` implementation extends the signature of
    the wrapped callable with additional keyword-arguments, default values
    deviating from the result handler implementation defaults can be supplied
    via the ``extra_kwarg_defaults`` parameter for a particular wrapped
    callable.

    All parameters given to the decorator are attached as attributes of the
    callable returned by the decorator, under the same name. For example, a
    parameter preprocessor is accessible as ``<wrapped>.preproc``.
    """

    def __init__(
        self,
        *,
        preproc: ParamProcessor | None = None,
        postproc_cls: ResultHandler | None = None,
        extra_kwarg_defaults: dict[str, Any] | None = None,
    ):
        self.preproc = preproc
        self.postproc_cls = postproc_cls or get_default_result_handler()
        self.extra_kwargs_defaults = extra_kwarg_defaults or {}

    def __call__(self, wrapped):
        @wraps(wrapped)
        def command_wrapper(*args, **kwargs):
            # TODO: there is no reason why `preproc` should not also be
            # able to add kwargs
            extra_kwarg_specs = self.postproc_cls.get_extra_kwargs()

            # join the given command kwargs with the extra kwargs defined
            # by the result handler
            kwargs = update_with_extra_kwargs(
                extra_kwarg_specs,
                self.extra_kwargs_defaults,
                **kwargs,
            )
            # produce a single dict (parameter name -> parameter value)
            # from all parameter sources
            allkwargs, params_at_default = get_allargs_as_kwargs(
                wrapped,
                args,
                kwargs,
                extra_kwarg_specs,
            )
            # preprocess the ful parameterization
            if self.preproc is not None:
                allkwargs = self.preproc(
                    allkwargs,
                    at_default=params_at_default,
                )

            # create a result handler instance for this particular
            # parameterization
            result_handler = self.postproc_cls(
                cmd_kwargs=allkwargs,
            )

            # let the result handler drive the underlying command and
            # let it do whatever it considers best to do with the
            # results
            return result_handler(
                # we wrap the result generating function into
                # a partial to get an argumentless callable
                # that provides an iterable. partial is a misnomer
                # here, all necessary parameters are given
                partial(
                    wrapped,
                    **{
                        k: v for k, v in allkwargs.items() if k not in extra_kwarg_specs
                    },
                ),
            )

        # update the signatured of the wrapped function to include
        # the common kwargs
        sig = signature(wrapped)
        sig = sig.replace(
            parameters=(
                *sig.parameters.values(),
                *self.postproc_cls.get_extra_kwargs().values(),
            ),
        )
        command_wrapper.__signature__ = sig

        # make decorator parameterization accessible to postprocessing
        # consumers
        command_wrapper.preproc = self.preproc
        command_wrapper.extra_kwargs_defaults = self.extra_kwargs_defaults
        # we make the result handler for a command known, so that
        # some kind of API could see whether it can further wrap a command
        # with another handler for something, and based on the type of
        # handler used here, it would be able to rely on particular behaviors,
        # or even refuse to consider a particular command
        command_wrapper.postproc_cls = self.postproc_cls
        return command_wrapper


def update_with_extra_kwargs(
    handler_kwarg_specs: dict[str, Parameter],
    deco_kwargs: dict[str, Any],
    **call_kwargs,
) -> dict[str, Any]:
    """Helper to update command kwargs with additional arguments

    Two sets of additional arguments are supported:

    - kwargs specifications (result handler provided) to extend the signature
      of an underlying command
    - ``extra_kwarg_defaults`` (given to the ``datalad_command`` decorator)
      that override the defaults of handler-provided kwarg specifications
    """
    # retrieve common options from kwargs, and fall back on the command
    # class attributes, or general defaults if needed
    updated_kwargs = {
        p_name: call_kwargs.get(
            # go with any explicitly given value
            p_name,
            # otherwise ifall back on what the command has been decorated with
            deco_kwargs.get(
                p_name,
                # or lastly go with the implementation default
                param.default,
            ),
        )
        for p_name, param in handler_kwarg_specs.items()
    }
    return dict(call_kwargs, **updated_kwargs)


def get_allargs_as_kwargs(call, args, kwargs, extra_kwarg_specs):
    """Generate a kwargs dict from a call signature and actual parameters

    The first return value is a mapping of all argument names to their
    respective values.

    The second return value is a set of argument names for which the effective
    value is identical to the default declared in the signature of the
    callable (or extra kwarg specification).
    """
    # we base the parsing off of the callables signature
    params = dict(signature(call).parameters.items())
    # and also add the common parameter definitions to get a joint
    # parameter set inspection
    params.update(extra_kwarg_specs)

    args = list(args)
    allkwargs = {}
    at_default = set()
    missing_args = []
    for pname, param in params.items():
        val = args.pop(0) if len(args) else kwargs.get(pname, param.default)
        allkwargs[pname] = val
        if val == param.default:
            at_default.add(pname)
        if val is param.empty:
            missing_args.append(pname)

    if missing_args:
        ma = missing_args
        multi_ma = len(ma) > 1
        # imitate standard TypeError message
        msg = (
            f'{call.__name__}() missing {len(ma)} required '
            f'positional argument{"s" if multi_ma else ""}: '
            f'{", ".join(repr(a) for a in ma[:-1 if multi_ma else None])}'
        )
        if multi_ma:
            msg += f' and {ma[-1]!r}'
        raise TypeError(msg)

    return allkwargs, at_default
