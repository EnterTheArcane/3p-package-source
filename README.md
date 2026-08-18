# O3DE third-party packages

This repository builds the prebuilt third-party libraries that O3DE downloads at
configure time. Conan 2 resolves and builds the dependency graph; the repository's
deployer converts every resolved Conan binary into the four files expected by O3DE's
package server.

## Setup

Install the pinned Conan and Ninja versions, then register this checkout as a local
recipes index:

```bash
pip install .
conan remote add o3de "$(pwd)" \
    --type=local-recipes-index --index=0 --force --allowed-packages="*"
```

`o3de` has first priority. Recipes in this checkout therefore override recipes with the
same reference in Conan Center, while requirements not present here fall through to
Conan Center normally. Built binaries use the regular Conan cache; no alternate Conan
home, workspace, recipe export step, or package server is required.

List the available O3DE recipes:

```bash
conan list '*' -r=o3de
```

## Build and package

`conan install` builds a requested package and any missing dependencies, then invokes the
deployer. For example, on Apple Silicon:

```bash
conan install --requires=qt/6.10.2 \
    -pr:h=profiles/mac-arm -pr:b=profiles/mac-arm \
    --update --build=missing \
    --output-folder=build/mac-arm --envs-generation=false \
    --deployer=extensions/deployers/engine_package.py \
    --deployer-folder=packages/mac-arm
```

Every host dependency is emitted as its own O3DE package. Recipes use `validate()` to
reject targets O3DE does not build; `conan graph info` can preflight a recipe/profile pair
without treating an invalid configuration as a command failure.

Keep `--update` when working from the local index. It makes Conan notice a new recipe
revision even when that reference already exists in the local cache.

Validate the resulting package contract with:

```bash
python3 tools/validate_package.py packages/mac-arm
python3 tools/engine_check.py packages/mac-arm --engine ../o3de
```

To consume the local packages from an engine checkout:

```bash
cmake -B build -S . \
    -DLY_PACKAGE_SERVER_URLS=file:///absolute/path/to/3PS/packages/mac-arm
```

## Immutable package names

Conan identifies a binary with its recipe revision, package ID, and package revision.
O3DE archives follow the same content-addressed idea:

```text
<name>-<version>-<o3de-platform>-<deployment-id>
```

The deployment digest includes the complete Conan binary reference, packaged payload,
generated or curated CMake files, descriptor metadata, file modes and the deployer. A
recipe can keep the same semantic version while a changed build receives a new CDN-safe
name automatically. The filename uses the first 24 hexadecimal characters (96 bits) of
the digest; the complete SHA-256 remains in `packages-manifest.json`, while the engine
separately pins and verifies the complete SHA-256 of the archive. At one million distinct
artifacts, the probability of an accidental 96-bit prefix collision is approximately
6e-18. There is no manually maintained `rev` field.

## Repository layout

```text
recipes/<name>/config.yml                 Conan local-index version mapping
recipes/<name>/all/conanfile.py           shared Conan recipe implementation
profiles/                                 O3DE target profiles
extensions/deployers/engine_package.py    Conan graph to O3DE archives
tools/validate_package.py                 archive and CMake contract validation
tools/engine_check.py                     end-to-end engine package resolution
tools/gen_builtin_packages.py             engine package-pin generation
docs/                                     package and release documentation
```

See [adding a package](docs/adding-a-package.md), [platforms](docs/platforms.md), and the
[release process](docs/release-process.md) for the longer workflows.

## Licensing

Package licenses come from Conan recipes and travel inside each deployed package, with
their paths recorded in `PackageInfo.json`. This repository is licensed under
Apache-2.0 OR MIT; see [LICENSE.txt](LICENSE.txt).
