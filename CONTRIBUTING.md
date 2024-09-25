# Contributing to `datalad-core`

- [What contributions are most suitable for `datalad-core`](#when-should-i-consider-a-contribution-to-datalad-core)
- [Developer cheat sheet](#developer-cheat-sheet)
- [Style guide](#contribution-style-guide)
- [CI workflows](#ci-workflows)


## When should I consider a contribution to `datalad-core`?

This package aims to be a lightweight library, to be used by any and all DataLad packages.
Contributed code should match this scope.
Special-interested functionality or code concerned with individual services and packages should be contributed elsewhere.
Morever, additional software dependencies should not be added carelessly -- a reasonably small dependency footprint is a key goal of this library.

## Developer cheat sheet

[Hatch](https://hatch.pypa.io) is used as a convenience solution for packaging and development tasks.
Hatch takes care of managing dependencies and environments, including the Python interpreter itself.
If not installed yet, installing via [pipx](https://github.com/pypa/pipx) is recommended (`pipx install hatch`).

Below is a list of some provided convenience commands.
An accurate overview of provided convenience scripts can be obtained by running: `hatch env show`.
All command setup can be found in `pyproject.toml`, and given alternatively managed dependencies, all commands can also be used without `hatch`.

### Run the tests (with coverage reporting)

```
hatch test [--cover]
```

There is also a setup for matrix test runs, covering all current Python versions:

```
hatch run tests:run [<select tests>]
```

This can also be used to run tests for a specific Python version only:

```
hatch run tests.py3.10:run [<select tests>]
```

### Build the HTML documentation (under `docs/_build/html`)

```
hatch run docs:build
# clean with
hatch run docs:clean
```

### Check type annotations

```
hatch run types:check [<paths>]
```

### Check commit messages for compliance with [Conventional Commits](https://www.conventionalcommits.org)

```
hatch run cz:check-commits
```

### Show would-be auto-generated changelog for the next release

Run this command to see whether a commit series yields a sensible changelog
contribution.

```
hatch run cz:show-changelog
```

### Create a new release

```
hatch run cz:bump-version
```

The new version is determined automatically from the nature of the (conventional) commits made since the last release.
A changelog is generated and committed.

In cases where the generated changelog needs to be edited afterwards (typos, unnecessary complexity, etc.), the created version tag needs to be advanced.


### Build a new source package and wheel

```
hatch build
```

### Publish a new release to PyPi

```
hatch publish
```

## Contribution style guide

A contribution must be complete with code, tests, and documentation.

`datalad-core` is a place for mature, and modular code.
Therefore, tests are essential.
A high test-coverage is desirable.
Contributors should clarify why a contribution is not covered 100%.
Tests must be dedicated for the code of a particular contribution.
It is not sufficient, if other code happens to also exercise a new feature.

New code should be type-annotated.
At minimum, a type annotation of the main API (e.g., function signatures) is needed.
A dedicated CI run is testing type annotations.

Docstrings should be complete with information on parameters, return values, and exception behavior.
Documentation should be added to and rendered with the sphinx-based documentation.

### Conventional commits

Commits and commit messages must be [Conventional Commits](https://www.conventionalcommits.org).
Their compliance is checked for each pull request.
The following commit types are recognized:

- `feat`: introduces a new feature
- `fix`: address a problem, fix a bug
- `doc`: update the documentation
- `rf`: refactor code with no change of functionality
- `perf`: enhance performance of existing functionality
- `test`: add/update/modify test implementations
- `ci`: change CI setup
- `style`: beautification
- `chore`: results of routine tasks, such as changelog updates
- `revert`: revert a previous change
- `bump`: version update

Any breaking change must have at least one line of the format

    BREAKING CHANGE: <summary of the breakage>

in the body of the commit message that introduces the breakage.
Breaking changes can be introduced in any type of commit.
Any number of breaking changes can be described in a commit message (one per line).
Breaking changes trigger a major version update, and form a dedicated section in the changelog.

### Pull-requests

The projects uses pull requests (PR) for contributions.
However, PRs are considered disposable, and no essential information must be uniquely available in PR descriptions and discussions.
All important (meta-)information must be in commit messages.
It is perfectly fine to post a PR with *no* additional description.

### Code organization

In `datalad-core`, all code is organized in shallow sub-packages.
Each sub-package is located in a directory within the `datalad_core` package.

Consequently, there are no top-level source files other than a few exceptions for technical reasons (`__init__.py`, `conftest.py`, `_version.py`).

A sub-package contains any number of code files, and a `tests` directory with all test implementations for that particular sub-package, and only for that sub-package.
Other, deeper directory hierarchies are not to be expected.

There is no limit to the number of files.
Contributors should strive for files with less than 500 lines of code.

Within a sub-package, tests should import the tested code via relative imports.

Code users should be able to import the most relevant functionality from the sub-package's `__init__.py`.
Only items importable from the sub-package's top-level are considered to be part of its "public" API.
If a sub-module is imported in the sub-package's `__init__.py`, consider adding `__all__` to the sub-module to restrict wildcard imports from the sub-module, and to document what is considered to be part of the "public" API.

Sub-packages should be as self-contained as possible.
If functionality is shared between sub-packages, absolute imports should be made.


### Imports

#### Import centralization per sub-package

If possible, sub-packages should have a "central" place for imports of functionality from outside `datalad-core` and the Python standard library.
Other sub-package code should then import from this place.
This aims to make external dependencies more obvious, and import-error handling and mitigation for missing dependencies simpler and cleaner.
Such a location could be the sub-package's `__init__.py`, or possibly a dedicated `dependencies.py`.

### Test output

Tests should be silent on stdout/stderr as much as possible.
In particular (but not only), result renderings of DataLad commands must no be produced, unless necessary for testing a particular feature.


## CI workflows

The addition of automation via CI workflows is welcome.
However, such workflows should not force developers to depend on, or have to wait for any particular service to run a workflow before they can discover essential outcomes.
When such workflows are added to online services, an equivalent setup for local execution should be added to the repository.
The `hatch` environments and tailored commands offer a straightforward, and discoverable method to fulfill this requirement (`hatch env show`).
