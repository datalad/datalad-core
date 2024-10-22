"""Constraints for command/function parameters"""

from __future__ import annotations

from abc import (
    ABC,
    abstractmethod,
)
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
    get_manager,
)
from datalad_core.constraints import (
    Constraint,
    ConstraintError,
    EnsureChoice,
)
from datalad_core.constraints.basic import (
    NoConstraint,
)

# register defaults of configuration supported by the code in this module
defaults = get_defaults()
defaults['datalad.runtime.parameter-violation'] = ConfigItem(
    'raise-early',
    coercer=EnsureChoice('raise-early', 'raise-at-end'),
)


class ParamProcessor(ABC):
    """Abstract base class for parameter processors

    Derived classes must implement `__call__()`, which receives two parameters:

    - ``kwargs``: a mapping of ``str`` parameter names to arbitrary values
    - ``at_default``: a ``set`` of parameter names, where the value given via
      ``kwargs`` is identical to the respective implementation default (i.e.,
      the default set in a function's signature.
    """

    @abstractmethod
    def __call__(
        self,
        kwargs: Mapping[str, Any],
        at_default: set[str] | None = None,
    ) -> Mapping[str, Any]:
        """ """


class JointParamProcessor(ParamProcessor):
    """Parameter preprocessor with support for multi-parameter set handling

    Typically, this processor is used with particular value :class:`Constraint`
    instances for individual parameters. For example, declaring that a ``mode``
    parameter must be one of a set of possible choices may look like this::

      >>> pp = JointParamProcessor({'mode': EnsureChoice('slow', 'fast')})
      >>> pp({'mode': 'slow'})
      {'mode': 'slow'}

    The respective parameter values will be passed "through" their constraint.
    When no constraint is given for a particular parameter, any input value
    is passed on as-is.

    There is one exception to this rule: When a parameter value is declared
    identical to its default value (e.g., as declared in the command signature)
    via the ``at_default`` argument of ``__call__()``), this default value is
    also passed on as-is.

    An important consequence of this behavior is that assigned constraints
    generally need not cover a default value. For example, a parameter
    constraint for ``mode=None`` -- where ``None`` is a special value used to
    indicate an optional and unset value, but actually only specific ``str``
    labels are acceptable input values -- can simply use something like
    ``EnsureChoice('a', 'b')``, and it is not necessary to do something like
    ``EnsureChoice('a', 'b', None)``.

    However, this class can also be specifically instructed to perform
    validation of defaults for individual parameters, by including any
    parameter name in the ``proc_defaults`` parameter.  A common use case is
    the auto-discovery of datasets, where often ``None`` is the default value
    of a `dataset` parameter (to make it optional), and an
    :class:`EnsureDataset` constraint is used. This constraint can perform the
    auto-discovery (with the ``None`` value indicating that), but validation of
    defaults must be turned on for the ``dataset`` parameter in order to do
    that.  and reraised immediately.

    With ``on_error``, the error handling during processing can be configured.
    When set to ``'raise-early'`` processing stops when encountering the first
    error and a :class:`ParamErrors` exception is raised. With
    ``'raise-at-end'`` processing continues (as far as possible), and potential
    additional errors are collected and raised jointly with a
    :class:`ParamErrors`. When set to ``None``, the error reporting mode is
    taken from the configuration setting
    ``datalad.runtime.parameter-violation``, which can take any of the
    aforementioned mode labels.

    A raised instance of the :class:`ParamErrors` exception, can report all
    individual issues found for a given parameter set in a structured
    fashion. This helps reporting such errors in an UI-appropriate manner.
    The gathering and structured reporting of errors is only supported for
    :class:`ConstraintError` exceptions raised by individual constraints.
    Any other exception is raise immediately.

    Higher-order parameter constraints
    ----------------------------------

    After per-parameter constraint processing, this class can perform
    additional (optional), higher-order parameter set constraint processing.
    This is a flexible mechanism that can be used to investigate the values of
    multiple parameters simultaneously. This feature can also be used to
    implement API transitions, because values can be moved from one parameter
    to another, and/or deprecation messages can be issued.

    Such multi-parameter processing is enabled by passing instances of
    :class:`ParamSetConstraint` to the ``paramset_constraints``
    keyword-argument. Each instance declares which parameters it will
    process and will receive the associated values as a mapping to its
    ``__call__()`` method.

    The order of :class:`ParamSetConstraint` instances given to
    ``paramset_constraints`` is significant. Later instances will receive the
    outcomes of the processing of earlier instances.

    Error handling for :class:`ParamSetConstraint` instances follows the
    same rules as described above, and ``on_error`` is honored in the same
    way.

    Automated tailoring of constraints to a specific dataset
    --------------------------------------------------------

    With ``tailor_for_dataset``, constraints for individual parameters can be
    automatically transformed to apply to the scope of a particular dataset.
    The value given to ``tailor_for_dataset`` has to be a mapping of names of
    parameters whose constraints should be tailored to a particular dataset, to
    the respective names parameters identifying these datasets.

    The dataset-providing parameter constraints will be evaluated first, and
    the resulting :class:`Dataset` instances are used to tailor the constraints
    that require a dataset-context, by calling their
    :meth:`~Constraint.for_dataset` method. Tailoring is performed if, and only
    if, the dataset-providing parameter actually evaluated to a `Dataset`
    instance. The non-tailored constraint is used otherwise.
    """

    def __init__(
        self,
        param_constraints: Mapping[str, Constraint],
        *,
        proc_defaults: Container[str] | None = None,
        paramset_constraints: Iterable[ParamSetConstraint] | None = None,
        tailor_for_dataset: Mapping[str, str] | None = None,
        on_error: str | None = None,
    ):
        super().__init__()
        self._param_constraints = param_constraints
        self._paramset_constraints = paramset_constraints
        self._proc_defaults = proc_defaults or set()
        self._tailor_for_dataset = tailor_for_dataset or {}
        if on_error is None:
            # consider configuration for immediate vs exhaustive processing
            on_error = (
                get_manager()
                .get(
                    'datalad.runtime.parameter-violation',
                    'raise-early',
                )
                .value
            )
        # TODO: migrate to coercer for config options
        if on_error not in ('raise-early', 'raise-at-end'):
            msg = "`on_error` must be 'raise-early' or 'raise-at-end'"
            raise ValueError(msg)
        self._on_error = on_error

    def __call__(
        self,
        kwargs: Mapping[str, Any],
        at_default: set[str] | None = None,
    ) -> Mapping[str, Any]:
        """Performs the configured processing on the given parameter values

        The ``kwargs`` mapping specifies the to-be-processed parameters and
        their values. Upon successful completion, the method will return
        such a mapping again.

        With ``at_default``, a subset of parameters can be identified by name,
        whose values are to be considered at their respective default values.
        This is only relevant for deciding whether to exclude particular
        values from constraint processing (see the ``proc_defaults``
        constructor argument).

        A :class:`ParamErrors` exception is raised whenever one or more
        :class:`ConstraintError` exceptions have been caught during processing.
        """
        on_error = self._on_error

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
                processed[pname] = self._proc_param(
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
            final = self._proc_param_sets(processed, on_error)
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

    def _proc_param(
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

    def _proc_param_sets(self, params: dict, on_error: str) -> dict:
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
                res = constraint({p: processed[p] for p in ctx.param_names})
            except ConstraintError as e:
                if (
                    not isinstance(e.value, dict)
                    or set(ctx.param_names) != e.value.keys()
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
