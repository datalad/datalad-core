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
    Callable,
)

from datalad_core.commands.default_result_handler import get_default_result_handler
from datalad_core.config import (
    ConfigItem,
    get_defaults,
    get_manager,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from datalad_core.commands.result_handler import ResultHandler


# TODO: move to the code that defines this
defaults = get_defaults()
defaults['datalad.runtime.parameter-violation'] = ConfigItem(
    'raise-early',
    # coercer=EnsureChoice('raise-early', 'raise-at-end'),
)


# this could be a function decorator, but we use a class, because
# it is less confusing to read (compared to the alternative decorator
# factory
class datalad_command:  # noqa: N801  MIH wants lower-case
    """Equip a function with parameter validation and result post-processing

    Wrapped commands must not have any positional-only parameters.
    """

    def __init__(
        self,
        *,
        param_validator=None,
        result_handler_cls: ResultHandler | None = None,
        extra_kwarg_defaults: dict[str, Any] | None = None,
    ):
        """
        ``param_validator``...

        ``result_handler_cls`` ...

        ``extra_kwargs_defaults`` can be used to override defaults for extra
        keyword arguments declared by the result handler.

        """
        self.param_validator = param_validator
        self.result_handler_cls = result_handler_cls or get_default_result_handler()
        self.extra_kwargs_defaults = extra_kwarg_defaults or {}

    def __call__(self, wrapped):
        @wraps(wrapped)
        def command_wrapper(*args, **kwargs):
            extra_kwarg_specs = self.result_handler_cls.get_extra_kwargs()

            # join the given command kwargs with the extra kwargs defined
            # by the result handler
            kwargs = update_with_extra_kwargs(
                extra_kwarg_specs,
                self.extra_kwargs_defaults,
                **kwargs,
            )
            # perform any validation on the joint parameterization.
            # return the full (validated) parameterization as a
            # single dict (parameter name -> parameter value) with all
            allkwargs = validate_parameters(
                param_validator=self.param_validator,
                cmd=wrapped,
                cmd_args=args,
                cmd_kwargs=kwargs,
                extra_kwarg_specs=extra_kwarg_specs,
            )

            # create a result handler instance for this particular
            # parameterization
            result_handler = self.result_handler_cls(
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
                *self.result_handler_cls.get_extra_kwargs().values(),
            ),
        )
        command_wrapper.__signature__ = sig

        # make decorator parameterization accessible to postprocessing
        # consumers
        command_wrapper.param_validator = self.param_validator
        command_wrapper.extra_kwargs_defaults = self.extra_kwargs_defaults
        # we make the result handler for a command known, so that
        # some kind of API could see whether it can further wrap a command
        # with another handler for something, and based on the type of
        # handler used here, it would be able to rely on particular behaviors,
        # or even refuse to consider a particular command
        command_wrapper.result_handler_cls = self.result_handler_cls
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

    Returns a ``dict`` and two ``set``.

    The first return value is a mapping of all argument names to their
    respective values.

    The second return value is a set of argument names for which the effective
    value is identical to the default declared in the signature of the
    callable (or extra kwarg specification).

    The third value is a set with names of all mandatory arguments, whether or
    not they are included in the returned mapping.
    """
    # we base the parsing off of the callables signature
    params = dict(signature(call).parameters.items())
    # and also add the common parameter definitions to get a joint
    # parameter set inspection
    params.update(extra_kwarg_specs)

    args = list(args)
    allkwargs = {}
    at_default = set()
    required = set()
    for pname, param in params.items():
        val = args.pop(0) if len(args) else kwargs.get(pname, param.default)
        allkwargs[pname] = val
        if val == param.default:
            at_default.add(pname)
        if param.default is param.empty:
            required.add(pname)
    return allkwargs, at_default, required


def validate_parameters(
    param_validator,
    cmd: Callable[..., Generator[dict, None, None]],
    cmd_args: tuple,
    cmd_kwargs: dict,
    extra_kwarg_specs,
) -> dict[str, Any]:
    # for result filters and validation
    # we need to produce a dict with argname/argvalue pairs for all args
    # incl. defaults and args given as positionals
    allkwargs, at_default, required_args = get_allargs_as_kwargs(
        cmd,
        cmd_args,
        cmd_kwargs,
        extra_kwarg_specs,
    )
    # validate the complete parameterization
    if param_validator is None:
        return allkwargs

    validator_kwargs = {
        'at_default': at_default,
        'required': required_args or None,
    }
    # make immediate vs exhaustive parameter validation
    # configurable
    validator_kwargs['on_error'] = get_manager()[
        'datalad.runtime.parameter-violation'
    ].value

    return param_validator(allkwargs, **validator_kwargs)
