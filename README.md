# datalad-core: core library for the DataLad framework

[![Documentation Status](https://readthedocs.org/projects/datalad-core/badge/?version=latest)](https://datalad-core.readthedocs.io/en/latest/?badge=latest)
[![Build status](https://ci.appveyor.com/api/projects/status/r115bg2iqtvymww4/branch/main?svg=true)](https://ci.appveyor.com/project/mih/datalad-core/branch/main)
[![codecov](https://codecov.io/github/datalad/datalad-core/graph/badge.svg?token=9RG02U6TY4)](https://codecov.io/github/datalad/datalad-core)


## Developing with `datalad_core`

API stability is important, just as adequate semantic versioning, and informative
changelogs.

### Public vs internal API

Anything that can be imported directly from any of the sub-packages in
`datalad_core` is considered to be part of the public API. Changes to this API
determine the versioning, and development is done with the aim to keep this API
as stable as possible. This includes signatures and return value behavior.

As an example: `from datalad_core.abc import xyz` imports a part of the public
API, but `from datalad_core.abc.def import xyz` does not.

### Use of the internal API

Developers can obviously use parts of the non-public API. However, this should
only be done with the understanding that these components may change from one
release to another, with no guarantee of transition periods, deprecation
warnings, etc.

Developers are advised to never reuse any components with names starting with
`_` (underscore). Their use should be limited to their individual subpackage.

## Contributing

Contributions to this library are welcome! Please see the [contributing
guidelines](CONTRIBUTING.md) for details on scope and style of potential
contributions.
