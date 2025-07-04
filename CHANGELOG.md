# v0.1.0 (2025-07-04)

## 💫 New features

- add dependency on git-annex [[d238e28e]](https://github.com/datalad/datalad-core/commit/d238e28e)
- `rmtree()` test helper [[b1f32026]](https://github.com/datalad/datalad-core/commit/b1f32026)
- test helper `modify_dataset()` and `modified_dataset` [[b4bb4e14]](https://github.com/datalad/datalad-core/commit/b4bb4e14)
- add test fixtures related to symlink capabilities [[57c9439d]](https://github.com/datalad/datalad-core/commit/57c9439d)
- add test helper `call_git_addcommit()` [[3c237dbe]](https://github.com/datalad/datalad-core/commit/3c237dbe)
- enhance `call_git()` to return captured output [[822b4f72]](https://github.com/datalad/datalad-core/commit/822b4f72)
- expose `EnsureDataset` in the `datalad_core.commands` module [[6393bec6]](https://github.com/datalad/datalad-core/commit/6393bec6)
- `EnsurePath` and `EnsureDatasetPath` [[257f35ed]](https://github.com/datalad/datalad-core/commit/257f35ed)
- parameter preprocessor (for `@datalad_command`) [[5d2b494a]](https://github.com/datalad/datalad-core/commit/5d2b494a)
- `EnsureChoice` constraint [[c8b55cc7]](https://github.com/datalad/datalad-core/commit/c8b55cc7)
- `EnsureDataset` constraint [[35a5eb98]](https://github.com/datalad/datalad-core/commit/35a5eb98)
- have `UnsetValue` be available from `consts` [[6a6045d1]](https://github.com/datalad/datalad-core/commit/6a6045d1)
- `EnsureMappingHasKeys` constraint [[a6d3ab97]](https://github.com/datalad/datalad-core/commit/a6d3ab97)
- `NoConstraint`, a constraint for representing no constraint [[b9caddfb]](https://github.com/datalad/datalad-core/commit/b9caddfb)
- add `Constraint.for_dataset()` to tailor constraints for a context [[93c54432]](https://github.com/datalad/datalad-core/commit/93c54432)
- allow for `Constraint` subclasses with no `input_description` [[343e8c76]](https://github.com/datalad/datalad-core/commit/343e8c76)
- `Dataset` class to represent a command's `dataset` parameter [[1741cc3f]](https://github.com/datalad/datalad-core/commit/1741cc3f)
- ensure `(Repo|Worktree).path` points to the respective root directory [[4917a2ae]](https://github.com/datalad/datalad-core/commit/4917a2ae)
- have flyweight be robust to (root-)path resolution [[4b468308]](https://github.com/datalad/datalad-core/commit/4b468308)
- `@datalad_command` decorator [[53519146]](https://github.com/datalad/datalad-core/commit/53519146)
- `ConfigManager.get_from_protected_sources()` [[9ab7305b]](https://github.com/datalad/datalad-core/commit/9ab7305b)
- new `ConfigManager(sources=...)` parameter [[6dd0e9dc]](https://github.com/datalad/datalad-core/commit/6dd0e9dc)
- `WithDescription` constraint wrapper to adjust auto-documentation [[f101949d]](https://github.com/datalad/datalad-core/commit/f101949d)
- foundational classes for constraints [[7da8bd43]](https://github.com/datalad/datalad-core/commit/7da8bd43)
- dedicated `ConstraintError` for structured reporting on validation errors [[f57385f0]](https://github.com/datalad/datalad-core/commit/f57385f0)
- annex interfaces and initialization [[93be2575]](https://github.com/datalad/datalad-core/commit/93be2575)
- `call_annex_json_lines()` utility [[a1feef64]](https://github.com/datalad/datalad-core/commit/a1feef64)
- repository/worktree initialization methods [[e432e31f]](https://github.com/datalad/datalad-core/commit/e432e31f)
- classes to represent (bare) Git repositories and worktrees [[228f8c67]](https://github.com/datalad/datalad-core/commit/228f8c67)
- configuration manager [[b9ac3d0e]](https://github.com/datalad/datalad-core/commit/b9ac3d0e)
- new `const` module with common, static definitions [[b03f5d82]](https://github.com/datalad/datalad-core/commit/b03f5d82)
- helper for executing (Git) subprocesses [[aaec4aa6]](https://github.com/datalad/datalad-core/commit/aaec4aa6)

## 🐛 Bug Fixes

- git-annex changed error reporting, adjust regex [[a56d124a]](https://github.com/datalad/datalad-core/commit/a56d124a)
- check for exactly one line in `call_git_oneline` [[364902fe]](https://github.com/datalad/datalad-core/commit/364902fe)
- let a `Worktree` config manager never be identical to a `Repo`'s [[c43f0629]](https://github.com/datalad/datalad-core/commit/c43f0629)
- initialize internal variable of `GitConfig` needed by `__repr__()` [[d1f81e4a]](https://github.com/datalad/datalad-core/commit/d1f81e4a)

## 📝 Documentation

- add missing documentation on annex initialization [[a7c7a7e4]](https://github.com/datalad/datalad-core/commit/a7c7a7e4)
- (dataset-)path resolution pattern for command implementations [[a380d68f]](https://github.com/datalad/datalad-core/commit/a380d68f)
- render documentation for `__call__()` methods also [[060a9752]](https://github.com/datalad/datalad-core/commit/060a9752)
- show inherited class members [[e87df53f]](https://github.com/datalad/datalad-core/commit/e87df53f)
- add maintainability badge [[b36dd784]](https://github.com/datalad/datalad-core/commit/b36dd784)
- Add official badge of Hatch to `README.md` [[ab85e206]](https://github.com/datalad/datalad-core/commit/ab85e206)

## 🛡 Tests

- verify `call_git_oneline()` always raises for anything but a single line [[45f5edd3]](https://github.com/datalad/datalad-core/commit/45f5edd3)
- use a dedicated path a worktree, no re-use [[b69476c3]](https://github.com/datalad/datalad-core/commit/b69476c3)

# v0.0.0

- Initial package setup without any functionality.
