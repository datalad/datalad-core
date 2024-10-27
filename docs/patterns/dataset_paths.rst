(Dataset-specific) path resolution
----------------------------------

If a command operates on an item on the file system that is identified by its
path, and can (optionally) operate in the context of a specific dataset, this
is achieved with two arguments: ``dataset``, and ``path``.  It can be the case
that only one of these parameters is needed (and occasionally even neither one
is required) for a specific command invocation, hence they are typically both
used with ``None`` default values.

The following parameter preprocessor setup for ``@datalad_command`` can be used
to guarantee that the function body of a command will always receive:

- a ``pathlib`` path object instance via the ``path`` argument
- a ``Dataset`` instance via the ``dataset`` argument from which an
  (optional) dataset context can be identified.

    >>> from datalad_core.commands import (
    ...     EnsureDataset,
    ...     JointParamProcessor,
    ... )
    >>> from datalad_core.constraints import EnsurePath
    >>> preproc=JointParamProcessor(
    ...     {
    ...         'dataset': EnsureDataset(),
    ...         'path': EnsurePath()
    ...     },
    ...     proc_defaults={'dataset', 'path'},
    ...     tailor_for_dataset={
    ...         'path': 'dataset',
    ...     }
    ... ),

The above pattern takes care of resolving any path given to ``path``
(including ``None``) to an actual path. This path is adequately determined,
also considering the value of any ``dataset`` parameter. This follows
the conventions of path resolution in DataLad:

- any absolute path is taken as-is
- any relative path is interpreted as relative to CWD, unless there is
  a dataset context based on a :class:`Worktree` instance. Only in the
  latter case a relative path is interpreted as relative to the
  worktree root

Technically, this pattern works, because

- even ``None`` defaults will be processed for ``dataset`` and ``path``
- the ``tailored_for_dataset`` mapping causes the ``dataset`` argument
  to be resolved first (before ``path``)
- and the :class:`EnsurePath` constraint is tailored to any :class:`Dataset`
  given to ``dataset``, by generating a matching :class:`EnsureDatasetPath`
  constraint for the ``path`` parameter internally

Taken together, this pattern simplifies command implementation, because
a number of checks are factored out into common implementation following
accepted conventions. Command implementations can inspect the specifics
of a user-provided dataset context via :attr:`Dataset.pristine_spec`.
