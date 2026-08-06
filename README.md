# O3DE third party packages

This repository builds the prebuilt third party libraries that O3DE downloads at configure
time. A package built here is a `.tar.xz` the engine fetches from a package server,
unpacks, and resolves with `find_package`; nothing about that contract has changed.

What has changed is how the packages are produced. Recipes, profiles and dependency
resolution are [Conan 2](https://docs.conan.io/2/); a deployer turns the resolved graph
into the package layout the engine expects. Libraries that Conan Center already packages
well are consumed from there, and this repository holds a recipe only where the engine
needs something Conan Center does not provide.

## Getting started

```bash
pip install "conan==2.31.*"

python3 tools/3rdparty.py platforms              # target platforms and their package counts
python3 tools/3rdparty.py packages mac-arm       # what is built for one of them
python3 tools/3rdparty.py package mac-arm        # build and package everything for it
python3 tools/3rdparty.py validate mac-arm       # check the results against the engine contract
```

`package` writes to `packages/<platform>/`: four files per package, plus a manifest.

To use them in an engine before anything is published, point it at that folder:

```bash
cmake -B build -S . -DLY_PACKAGE_SERVER_URLS=file:///path/to/3PS/packages/mac-arm
```

`tools/gen_builtin_packages.py` rewrites an engine checkout's package pins to match a
built folder, which is what the promote workflow does when it opens its pull request.

## Layout

```
recipes/<name>/      package.yml, and a conanfile.py only when we build it ourselves
profiles/            one per target platform, plus _common
consumer/            the aggregate that resolves a whole platform at once
extensions/deployers/engine_package.py    turns resolved packages into engine packages
tools/               the command line, the catalog, the validators
docs/                the longer explanations
.github/workflows/   build, promote, lockfile maintenance
```

Every package is described by `recipes/<name>/package.yml`: its version, its `rev`, the
CMake targets it answers to, and which platforms want it. A `conanfile.py` beside it means
we build that one ourselves; without one, the recipe comes from Conan Center.

## Documentation

- [Adding a package](docs/adding-a-package.md) — the fields, when a recipe is needed, and
  why every dependency has to be accounted for
- [Platforms](docs/platforms.md) — the eleven targets and what builds them
- [Release process](docs/release-process.md) — how packages reach the CDN and the engine
- [Migration status](docs/migration-status.md) — which recipes are ours and why, and the
  problems that cost enough time to be worth writing down

## Licensing

Package licenses come from the recipes and travel inside each package, with the path
recorded in its `PackageInfo.json`. This repository is licensed under Apache-2.0 OR MIT;
see [LICENSE.txt](LICENSE.txt).
