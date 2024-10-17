from __future__ import annotations

from textwrap import indent
from types import MappingProxyType
from typing import (
    Any,
)


class ConstraintError(ValueError):
    # we derive from ValueError, because it provides the seemingly best fit
    # of any built-in exception. It is defined as:
    #
    #   Raised when an operation or function receives an argument that has
    #   the right type but an inappropriate value, and the situation is not
    #   described by a more precise exception such as IndexError.
    #
    # In general a validation error can also occur because of a TypeError, but
    # ultimately what also matters here is an ability to coerce a given value
    # to a target type/value, but such an exception is not among the built-ins.
    # Moreover, many pieces of existing code do raise ValueError in practice,
    # and we aim to be widely applicable with this specialized class
    """Exception type raised by constraints when their conditions are violated

    A primary purpose of this class is to provide uniform means for
    communicating structured information on violated constraints.

    """

    def __init__(
        self,
        constraint,
        value: Any,
        msg: str,
        ctx: dict[str, Any] | None = None,
    ):
        """
        Parameters
        ----------
        constraint: Constraint
          Instance of the ``Constraint`` class that determined a violation.
        value:
          The value that is in violation of a constraint.
        msg: str
          A message describing the violation. If ``ctx`` is given too, the
          message can contain keyword placeholders in Python's ``format()``
          syntax that will be applied on-access.
        ctx: dict, optional
          Mapping with context information on the violation. This information
          is used to interpolate a message, but may also contain additional
          key-value mappings. A recognized key is ``'__caused_by__'``, with
          a value of one exception (or a tuple of exceptions) that led to a
          ``ConstraintError`` being raised.
        """
        # the msg/ctx setup is inspired by pydantic
        # we put `msg` in the `.args` container first to match where
        # `ValueError` would have it. Everything else goes after it.
        super().__init__(msg, constraint, value, ctx)

    @property
    def msg(self):
        """Obtain an (interpolated) message on the constraint violation

        The error message template can be interpolated with any information
        available in the error context dict (``ctx``). In addition to the
        information provided by the ``Constraint`` that raised the error,
        the following additional placeholders are provided:

        - ``__value__``: the value reported to have caused the error
        - ``__itemized_causes__``: an indented bullet list str with on
          item for each error in the ``caused_by`` report of the error.

        Message template can use any feature of the Python format mini
        language. For example ``{__value__!r}`` to get a ``repr()``-style
        representation of the offending value.
        """
        msg_tmpl = self.args[0]
        # get interpolation values for message formatting
        # we need a copy, because we need to mutate the dict
        ctx = dict(self.context)
        # support a few standard placeholders
        # the verbatim value that caused the error: with !r and !s both
        # types of stringifications are accessible
        ctx['__value__'] = self.value
        if self.caused_by:
            ctx['__itemized_causes__'] = indent(
                '\n'.join(f'- {c!s}' for c in self.caused_by),
                '  ',
            )
        return msg_tmpl.format(**ctx)

    @property
    def constraint(self):
        """Get the instance of the constraint that was violated"""
        return self.args[1]

    @property
    def caused_by(self) -> tuple[Exception] | None:
        """Returns a tuple of any underlying exceptions"""
        cb = self.context.get('__caused_by__', None)
        if cb is None:
            return None
        if isinstance(cb, Exception):
            return (cb,)
        return tuple(cb)

    @property
    def value(self):
        """Get the value that violated the constraint"""
        return self.args[2]

    @property
    def context(self) -> MappingProxyType:
        """Get a constraint violation's context

        This is a mapping of key/value-pairs matching the ``ctx`` constructor
        argument.
        """
        return MappingProxyType(self.args[3] or {})

    def __str__(self) -> str:
        return self.msg

    def __repr__(self) -> str:
        # rematch constructor arg-order, because we put `msg` first into
        # `.args`
        return '{0}({2!r}, {3!r}, {1!r}, {4!r})'.format(
            self.__class__.__name__,
            *self.args,
        )
