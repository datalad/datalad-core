"""Constraints for command/function parameters"""

from __future__ import annotations

from itertools import chain
from typing import (
    TYPE_CHECKING,
    Any,
)

if TYPE_CHECKING:
    from collections.abc import (
        Container,
        Iterable,
        Mapping,
    )

    from datalad_core.commands.param_constraint import ParamSetConstraint

from datalad_core.commands.dataset import Dataset
from datalad_core.commands.exceptions import (
    ParamConstraintContext,
    ParamErrors,
)
from datalad_core.config import (
    ConfigItem,
    get_defaults,
)
from datalad_core.constraints import (
    Constraint,
    ConstraintError,
)
from datalad_core.constraints.basic import (
    NoConstraint,
)

# register defaults of configuration supported by the code in this module
defaults = get_defaults()
defaults['datalad.runtime.parameter-violation'] = ConfigItem(
    'raise-early',
    # coercer=EnsureChoice('raise-early', 'raise-at-end'),
)


class ParamProcessor:
    """Basic implementation of a ``@datalad_command`` parameter validator

    This class can be used as-is, by declaring individual constraints
    in the constructor, or it can be subclassed to consolidate all
    custom validation-related code for a command in a single place.

    Commonly this constraint is used by declaring particular value constraints
    for individual parameters as a mapping. Declaring that the ``path``
    parameter should receive something that is or can be coerced to
    a valid ``Path`` object looks like this::

      ParamProcessor({'path': EnsurePath()})

    This class differs from a standard ``Constraint`` implementation,
    because its ``__call__()`` method support additional arguments
    that are used by the internal ``Interface`` handling code to
    control how parameters are validated.

    During validation, when no validator for a particular parameter is
    declared, any input value is passed on as-is, and otherwise an input is
    passed through the validator.

    There is one exception to this rule: When a parameter value is identical to
    its default value (as declared in the command signature, and communicated
    via the ``at_default`` argument of ``__call__()``), this default
    value is also passed as-is, unless the respective parameter name is
    included in the ``proc_defaults`` constructor argument.

    An important consequence of this behavior is that validators need
    not cover a default value. For example, a parameter constraint for
    ``path=None``, where ``None`` is a special value used to indicate an
    optional and unset value, but actually only paths are acceptable input
    values. can simply use ``EnsurePath()`` and it is not necessary to do
    something like ``EnsurePath() | EnsureNone()``.

    However, `ParamProcessor` can also be specifically
    instructed to perform validation of defaults for individual parameters, as
    described above.  A common use case is the auto-discovery of datasets,
    where often `None` is the default value of a `dataset` parameter (to make
    it optional), and an `EnsureDataset` constraint is used. This constraint
    can perform the auto-discovery (with the `None` value indicating that), but
    validation of defaults must be turned on for the `dataset` parameter in
    order to do that.

    A second difference to a common ``Constraint`` implementation is the
    ability to perform an "exhaustive validation" on request (via
    ``__call__(on_error=...)``). In this case, validation is not stopped at the
    first discovered violation, but all violations are collected and
    communicated by raising a ``ParamErrors`` exception, which
    can be inspected by a caller for details on number and nature of all
    discovered violations.

    Exhaustive validation and joint reporting are only supported for individual
    constraint implementations that raise `ConstraintError` exceptions. For
    legacy constraints, any raised exception of another type are not caught
    and reraised immediately.
    """

    def __init__(
        self,
        param_constraints: Mapping[str, Constraint],
        *,
        proc_defaults: Container[str] | None = None,
        paramset_constraints: Iterable[ParamSetConstraint] | None = None,
        tailor_for_dataset: Mapping[str, str] | None = None,
    ):
        """
        Parameters
        ----------
        param_constraints: dict
          Mapping of parameter names to parameter constraints. On validation
          an ``EnsureParameterConstraint`` instance will be created for
          each item in this dict.
        proc_defaults: container(str), optional
          If given, this is a set of parameter names for which the default
          rule, to not validate default values, does not apply and
          default values shall be passed through a given validator.
        paramset_constraints: dict, optional
          Specification of higher-order constraints considering multiple
          parameters together. See the ``joint_validation()`` method for
          details. Constraints will be processed in the order in which
          they are declared in the mapping. Earlier validators can modify
          the parameter values that are eventually passed to validators
          executed later.
        tailor_for_dataset: dict, optional
          If given, this is a mapping of a name of a parameter whose
          constraint should be tailored to a particular dataset, to a name
          of a parameter providing this dataset. The dataset-providing
          parameter constraints will be evaluated first, and the resulting
          Dataset instances are used to tailor the constraints that
          require a dataset-context. The tailoring is performed if, and
          only if, the dataset-providing parameter actually evaluated
          to a `Dataset` instance. The non-tailored constraint is used
          otherwise.
        """
        super().__init__()
        self._param_constraints = param_constraints
        self._paramset_constraints = paramset_constraints
        self._proc_defaults = proc_defaults or set()
        self._tailor_for_dataset = tailor_for_dataset or {}

    def __call__(
        self,
        kwargs: Mapping[str, Any],
        at_default: set | None = None,
        on_error: str = 'raise-early',
    ) -> dict:
        """
        Parameters
        ----------
        kwargs: dict
          Parameter name (``str``)) to value (any) mapping of the parameter
          set.
        at_default: set or None
          Set of parameter names where the respective values in ``kwargs``
          match their respective defaults. This is used for deciding whether
          or not to process them with an associated value constraint (see the
          ``proc_defaults`` constructor argument).
        on_error: {'raise-early', 'raise-at-end'}
          Flag how to handle constraint violation. By default, validation is
          stopped at the first error and an exception is raised. When an
          exhaustive validation is performed, an eventual exception contains
          information on all constraint violations. Regardless of this mode
          more than one error can be reported (in case (future) implementation
          perform independent validations in parallel).

        Raises
        ------
        ParamErrors
          Raised whenever one (or more) ``ConstraintError`` exceptions are
          caught during validation. Other exception types are not caught and
          pass through.
        """
        # TODO: register default
        if on_error not in ('raise-early', 'raise-at-end'):
            msg = "`on_error` must be 'raise-early' or 'raise-at-end'"
            raise ValueError(msg)

        exceptions: dict[ParamConstraintContext, ConstraintError] = {}

        # names of parameters we need to process
        to_process = set(kwargs)
        # check for any dataset that are required for tailoring other parameters
        ds_provider_params = set(self._tailor_for_dataset.values())
        # take these out of the set of parameters to validate, because we need
        # to process them first.
        # the approach is to simply sort them first, but otherwise apply standard
        # handling
        to_process.difference_update(ds_provider_params)
        # strip all args provider args that have not been provided
        ds_provider_params.intersection_update(kwargs)

        processed: dict[str, Any] = {}
        failed_to_process = set()
        # process all parameters. starts with those that are needed as
        # dependencies for others.
        # this dependency-based sorting is very crude for now. it does not
        # consider possible dependencies within `ds_provider_params` at all
        for pname in chain(ds_provider_params, to_process):
            try:
                processed[pname] = self.proc_param(
                    name=pname,
                    value=kwargs[pname],
                    at_default=at_default is not None and pname in at_default,
                    processed=processed,
                )
            # we catch only ConstraintError -- only these exceptions have what
            # we need for reporting. If any validator chooses to raise
            # something else, we do not handle it here, but let it bubble up.
            # it may be an indication of something being wrong with processing
            # itself
            except ConstraintError as e:
                # standard exception type, record and proceed
                exceptions[ParamConstraintContext((pname,))] = e
                if on_error == 'raise-early':
                    raise ParamErrors(exceptions) from e
                # we record this for an easy check whether it is worth proceeding
                # with higher order processing
                failed_to_process.add(pname)

        # do not bother with joint processing when the set of expected
        # arguments is not complete
        expected_for_proc_param_sets: set[str] = set()
        for c in self._paramset_constraints or []:
            expected_for_proc_param_sets.update(c.param_names)

        if expected_for_proc_param_sets.intersection(failed_to_process):
            raise ParamErrors(exceptions)

        try:
            # call (subclass) method to perform holistic, cross-parameter
            # processing of the full parameterization
            final = self.proc_param_sets(processed, on_error)
            # ATTN: we do not want to test for equivalence of keys in
            # `processed` and `final`. And is desirable for a preprocessor
            # to add or remove parameters from the parameter set that goes
            # on to an eventually callable.
        except ParamErrors as e:
            # we can simply suck in the reports, the context keys do not
            # overlap, unless the provided validators want that for some
            # reason
            exceptions.update(e.errors)

        if exceptions:
            raise ParamErrors(exceptions)

        return final

    def proc_param(
        self,
        name: str,
        value: Any,
        at_default: bool,  # noqa: FBT001
        processed: Mapping[str, Any],
    ) -> Any:
        if at_default and name not in self._proc_defaults:
            # do not validate any parameter where the value matches the
            # default declared in the signature. Often these are just
            # 'do-nothing' settings or have special meaning that need
            # not be communicated to a user. Not validating them has
            # two consequences:
            # - the condition can simply be referred to as "default
            #   behavior" regardless of complexity
            # - a command implementation must always be able to handle
            #   its own defaults directly, and cannot delegate a
            #   default value handling to a constraint
            #
            # we must nevertheless pass any such default value through
            # to make/keep them accessible to the general result handling
            # code
            return value

        # look-up validator for this parameter, if there is none use
        # NoConstraint to avoid complex conditionals in the code below
        validator = self._param_constraints.get(name, NoConstraint())

        # do we need to tailor this constraint for a specific dataset?
        # only do if instructed AND the respective other parameter
        # processed to a Dataset instance. Any such parameter was sorted
        # to be processed first in this loop, so the outcome of that is
        # already available
        tailor_for = self._tailor_for_dataset.get(name)
        if tailor_for and isinstance(processed.get(tailor_for), Dataset):
            validator = validator.for_dataset(processed[tailor_for])

        return validator(value)

    def proc_param_sets(self, params: dict, on_error: str) -> dict:
        """Higher-order validation considering multiple parameters at a time

        This method is called with all, individually validated, command
        parameters in keyword-argument form in the ``params`` dict argument.

        Arbitrary additional validation steps can be performed on the full
        set of parameters that may involve raising exceptions on validation
        errors, but also value transformation or replacements of individual
        parameters based on the setting of others.

        The parameter values returned by the method are passed on to the
        respective command implementation.

        The default implementation iterates over the ``paramset_constraints``
        specification given to the constructor, in order to perform
        any number of validations. This is a mapping of a
        ``ParamConstraintContext`` instance to a callable implementing a
        validation for a particular parameter set.

        Example::

          _joint_validators_ = {
              ParamConstraintContext(('p1', 'p2'), 'sum'): MyValidator._check_sum,
          }


          def _checksum(self, p1, p2):
              if (p1 + p2) < 3:
                  self.raise_for(
                      dict(p1=p1, p2=p2),
                      'parameter sum is too large',
                  )

        The callable will be passed the arguments named in the
        ``ParamConstraintContext`` as keyword arguments, using the same
        names as originally given to ``ParamProcessor``.

        Any raised ``ConstraintError`` is caught and reported together with the
        respective ``ParamConstraintContext``. The violating value reported
        in such a ``ConstraintError`` must be a mapping of parameter name to
        value, comprising the full parameter set (i.e., keys matching the
        ``ParamConstraintContext``).  The use of ``self.raise_for()`` is
        encouraged.

        If the callable anyhow modifies the passed arguments, it must return
        them as a kwargs-like mapping.  If nothing is modified, it is OK to
        return ``None``.

        Returns
        -------
        dict
          The returned dict must have a value for each item passed in via
          ``params``.
        on_error: {'raise-early', 'raise-at-end'}
          Flag how to handle constraint violation. By default, validation is
          stopped at the first error and an exception is raised. When an
          exhaustive validation is performed, an eventual exception contains
          information on all constraint violations.

        Raises
        ------
        ParamErrors
          With `on_error='raise-at-end'` an implementation can choose to
          collect more than one higher-order violation and raise them
          as a `ParamErrors` exception.
        """
        exceptions = {}
        processed = params.copy()

        for constraint in self._paramset_constraints or []:
            ctx = constraint.context
            # what the validator will produce
            res = None
            try:
                # call the validator with the parameters given in the context
                # and only with those, to make sure the context is valid
                # and not an underspecification.
                # pull the values form `processed` to be able to benefit
                # from incremental coercing done in individual checks
                res = constraint({p: processed[p] for p in ctx.parameters})
            except ConstraintError as e:
                if (
                    not isinstance(e.value, dict)
                    or set(ctx.parameters) != e.value.keys()
                ):  # pragma: no cover
                    msg = (
                        'on raising a ConstraintError the joint validator '
                        f'{constraint} did not report '
                        'a mapping of parameter name to (violating) value '
                        'comprising all constraint context parameters. '
                        'This is a software defect of the joint validator. '
                        'Please report!'
                    )
                    raise RuntimeError(msg) from e
                exceptions[ctx] = e
                if on_error == 'raise-early':
                    raise ParamErrors(exceptions) from e
            if res is not None:
                processed.update(**res)

        if exceptions:
            raise ParamErrors(exceptions)

        return processed
