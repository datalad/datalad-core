import pytest

from datalad_core.commands.dataset import (
    Dataset,
    EnsureDataset,
)
from datalad_core.commands.exceptions import (
    ParamConstraintContext,
    ParamErrors,
)
from datalad_core.commands.param_constraint import ParamSetConstraint
from datalad_core.commands.preproc import JointParamProcessor
from datalad_core.constraints import (
    Constraint,
    ConstraintError,
    NoConstraint,
)


def test_paramcontext():
    ctx = ParamConstraintContext(
        param_names=('p1', 'p2'),
        description='key-aspect',
    )
    assert ctx.label == 'p1, p2 (key-aspect)'
    assert str(ctx) == f'Context[{ctx.label}]'


def test_paramprocessor_run_empty():
    pp = JointParamProcessor({})
    assert pp({}) == {}

    pp = JointParamProcessor({})
    params = {'something': 'value', 5: 'nonstr-key'}
    assert pp(params) == params

    with pytest.raises(ValueError, match="must be 'raise-early' or 'raise-at-end'"):
        JointParamProcessor({}, on_error='explode')


def test_paramprocessor_individual_param():
    class Not5(Constraint):
        input_synopsis = 'not 5'

        def __call__(self, val):
            if val != 5:  # noqa: PLR2004
                self.raise_for(val, self.input_synopsis)
            return val

    pp = JointParamProcessor(
        {
            'p1': Not5(),
        }
    )
    ok_case = {'p1': 5}
    assert ok_case == pp(ok_case)

    # TODO: add match=
    with pytest.raises(ParamErrors) as e:
        pp({'p1': 6})
    assert len(e.value.errors) == 1
    assert 'not 5' in str(e.value.errors[ParamConstraintContext(('p1',))])


def test_paramprocessor_multiparam_failure():
    class Err(Constraint):
        def __call__(self, val):
            self.raise_for(val, self.input_synopsis)

    class Err1(Err):
        input_synopsis = 'err1'

    class Err2(Err):
        input_synopsis = 'err2'

    class NeverReached(ParamSetConstraint):
        input_synopsis = 'irrelevant'

        def __call__(self, val):  # pragma: no cover
            # here could be test code
            return val

    pspecs = {
        'p1': Err1(),
        'p2': Err2(),
    }
    pp = JointParamProcessor(
        pspecs,
        paramset_constraints=(NeverReached(tuple(pspecs.keys())),),
        on_error='raise-at-end',
    )
    with pytest.raises(ParamErrors) as e:
        pp({'p1': 'ignored', 'p2': 'ignored'})
    assert len(e.value.errors) == len(pspecs)
    # smoke test
    assert repr(e.value.errors).startswith('mappingproxy(')
    assert set(e.value.messages) == {'err1', 'err2'}
    assert set(e.value.context_labels) == set(pspecs)
    exc_str = str(e.value)
    assert '2 parameter constraint violations' in exc_str
    assert 'err1' in exc_str
    assert 'err2' in exc_str


def test_paramprocessor_paramsets():
    class NotEqual(ParamSetConstraint):
        input_synopsis = 'parameters must not be all equal'

        def __call__(self, val):
            vals = [val[p] for p in self.param_names]
            if len(vals) != len(set(vals)):
                self.raise_for(
                    val,
                    'no all unique',
                )
            return val

    class OnlyCheck(ParamSetConstraint):
        input_synopsis = 'some potential checks'

        def __call__(self, val):
            # here could be test code
            return val

    pp_kwargs = {
        'param_constraints': {},
        'paramset_constraints': (
            NotEqual(('p1', 'p2'), aspect='identity'),
            OnlyCheck(('p1', 'p2', 'p3')),
        ),
    }
    pp = JointParamProcessor(**pp_kwargs)
    ok_case = {'p1': 5, 'p2': 4, 'p3': 3}
    fail_case = {'p1': 4, 'p2': 4, 'p3': 3}
    assert ok_case == pp(ok_case)

    pp = JointParamProcessor(on_error='raise-early', **pp_kwargs)
    with pytest.raises(ParamErrors) as e:
        pp(fail_case)

    # check composition of error
    exc_str = str(e.value)
    # summary
    assert '1 parameter constraint violation' in exc_str
    # subject of the error
    assert 'p1=4, p2=4 (identity)' in exc_str
    # nature of the error
    assert 'no all unique' in exc_str

    pp = JointParamProcessor(on_error='raise-at-end', **pp_kwargs)
    with pytest.raises(ParamErrors) as e:
        pp(fail_case)

    # composition of error does not change
    assert exc_str == str(e.value)


def test_paramprocessor_broken_constrainterror():
    class Broken(ParamSetConstraint):
        input_synopsis = 'cannot be satisfied'

        def __call__(self, val):  # noqa: ARG002
            # do not use raise_for() and intentionally
            # implement a broken replacement
            raise ConstraintError(self, 5, msg='broken')

    pp = JointParamProcessor(
        param_constraints={},
        paramset_constraints=(Broken(('p1', 'p2')),),
    )
    with pytest.raises(RuntimeError, match='software defect'):
        pp({'p1': 5, 'p2': None})


def test_paramprocessor_no_constrainterror():
    class Broken(Constraint):
        input_synopsis = 'raises alternative exception'

        def __call__(self, val):  # noqa: ARG002
            # any non-ConstraintError exception raised
            # would be an indication of an unexpected event,
            # even when validating
            msg = 'unexpected'
            raise AttributeError(msg)

    pp = JointParamProcessor(
        param_constraints={'p1': Broken()},
    )
    # exception is not hidden or transformed
    with pytest.raises(AttributeError, match='unexpected'):
        pp({'p1': 5})


def test_paramprocessor_no_proc_default():
    class Make5(Constraint):
        input_synopsis = 'turns everything to `5`'

        def __call__(self, val):  # noqa: ARG002
            return 5

    pp = JointParamProcessor(
        param_constraints={'p1': Make5()},
    )
    assert pp({'p1': 6}) == {'p1': 5}
    assert pp({'p1': 6}, at_default={'p1'}) == {'p1': 6}

    pp = JointParamProcessor(
        param_constraints={'p1': Make5()},
        proc_defaults={'p1'},
    )
    assert pp({'p1': 6}, at_default={'p1'}) == {'p1': 5}


def test_paramprocessor_tailor_for_dataset(gitrepo):
    class DsSubDir(Constraint):
        input_synopsis = 'give path in data'

        def __init__(self, ds):
            self._ds = ds

        def __call__(self, val):
            return self._ds.path / val

    # no need to be a NoConstraint, could also be EnsurePath, or any other
    # intermmediate validation step, but this is mostly for documentation.
    # So it would typically come wrapped into WithDescription
    class UntailoredDsSubDir(NoConstraint):
        input_synopsis = 'will produce a constraint that can do the job'

        def for_dataset(self, dataset):
            return DsSubDir(dataset)

    pp_kwargs = {
        'param_constraints': {
            'dataset': EnsureDataset(),
            'path': UntailoredDsSubDir(),
        },
        'tailor_for_dataset': {'path': 'dataset'},
    }
    pp = JointParamProcessor(**pp_kwargs)

    res = pp({'dataset': gitrepo, 'path': 'dummy'})
    assert res['dataset'].path == gitrepo
    assert res['path'] == gitrepo / 'dummy'

    # there is no tailoring, when 'dataset' does not come out as
    # a `Dataset` instance. Here we do not process the default value
    # so it is not happening
    res = pp({'dataset': None, 'path': 'dummy'}, at_default={'dataset'})
    assert res['dataset'] is None
    assert res['path'] == 'dummy'

    # but if we whitelist a parameter for default processing explicitly,
    # thing work again
    pp = JointParamProcessor(proc_defaults={'dataset'}, **pp_kwargs)
    res = pp({'dataset': None, 'path': 'dummy'}, at_default={'dataset'})
    assert res['path'] == Dataset(None).path / 'dummy'
