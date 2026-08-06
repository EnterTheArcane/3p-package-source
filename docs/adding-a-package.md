# Adding or changing a package

Every package is a directory under `recipes/` holding a `package.yml`. Whether we build
it ourselves is decided by one thing: if a `conanfile.py` sits beside that file, the
recipe is ours; if not, the recipe comes from Conan Center.

`package.yml` deliberately lives beside the recipe rather than inside it. Conan hashes a
recipe's exported files to decide whether a binary is still valid, so a rev bump written
into the conanfile would rebuild the package -- an hour, for Qt -- to change a number
that only affects publishing. Nothing in `package.yml` is exported, so editing it is free.

Run `tools/3rdparty.py packages` for the whole inventory in one view.

## A package that Conan Center already has

Create `recipes/libpng/package.yml` and you are done. No recipe, no build script.

```yaml
version: 1.6.58
rev: 1
targets: [PNG]
platforms: core
aliases:
  PNG: [PNG::PNG]
```

- `version` is the Conan version to require.
- `rev` is the release counter. The package name is `libpng-1.6.58-rev1-mac-arm`.
- `targets` are the names the engine passes to `find_package`. They keep their historic
  spelling (`PNG`, `TIFF`, `Freetype`, `GoogleBenchmark`) because engine and gem
  CMakeLists refer to `3rdParty::PNG` and friends.
- `platforms` selects where it is built: one of `all`, `core`, `desktop`, `tools`,
  `mobile`, `windows`, `web`, or a list of platform ids.
- `aliases` adds the upstream target spelling, so a dependency doing `find_package(PNG)`
  links ours instead of a system copy.

Then build and check it:

```bash
tools/3rdparty.py package mac-arm --only libpng
tools/3rdparty.py validate mac-arm
tools/engine_check.py packages/mac-arm --engine ../Engine
```

## A package that needs its own recipe

Add a `conanfile.py` next to the `package.yml`, written as an ordinary Conan recipe: package into the
normal `include/`, `lib/`, `bin/` layout and describe it in `package_info()`. The
deployer rearranges that into the engine's layout, so nothing about the engine belongs
in the recipe. `tools/3rdparty.py` exports every recipe under `recipes/` before it
builds, so a new directory needs no registration.

The presence of that file is what makes the package ours; nothing else changes.

While iterating on a recipe, `conan workspace add recipes/<name>` builds it from its
source directory instead of the cache. Remove it again before committing: a package
left in `conanws.yml` is never actually built into a package.

## When the generated CMake is not enough

By default the deployer writes `<name>-config.cmake` from the recipe's `package_info()`,
plus a `Find<target>.cmake` shim per target. That covers a library that is a set of
headers and archives.

It does not cover a package that has to *do* something at configure time: Qt defines
the `ly_qt_moc_target` family, and PySide installs itself into the engine's Python
environment. For those, put the real file in `recipes/<name>/cmake/` and it is copied
verbatim instead of being generated:

```
recipes/qt/cmake/qt-config.cmake     used instead of the generated config
recipes/qt/cmake/FindQt.cmake        used instead of the generated shim
```

Everything in that directory is copied to the package root, subdirectories included, so
Qt's `Platform/` files travel the same way.

Use `payload` when the payload directory should not be named after the recipe -- `"."`
puts the payload at the package root, which is how Python's framework has to arrive --
and
`bundle` to merge another package's payload into this one (OpenEXR ships Imath this way,
because the engine expects one package that answers to both names). When a package
bundles others and declares one target per package, each target is wired to its own
libraries rather than to everything in the archive.

## Every dependency has to be accounted for

Conan resolves a package's dependencies for the build, but the engine only ever sees the
packages we publish. Anything a package depends on and we do not ship has to either go
away or come along, or the engine fails much later and somewhere confusing: a missing
archive shows up as undefined symbols at link time, and a missing header shows up as a
compile error inside one of our own headers.

Prefer turning it off. `options` in `package.yml` are applied to the whole graph, and
most libraries make their format and codec backends optional -- libtiff builds against
nothing but zlib once its codecs are off, which is what the engine has always shipped.

Bundle what cannot be turned off. OpenEXR's recipe has no options at all, so libdeflate,
libjpeg, openjph and xz travel inside the package; OpenImageIO carries fmt and Imath
because its public headers include them by name. Bundling the same library into two
packages is only a problem if some engine target links both.

To find these before the engine does: `tools/validate_package.py` fails a package whose
binaries load anything from outside the package, which also catches a dependency picked
up from the build machine rather than from us.

## Changing a package that is already published

Published packages are immutable: the CDN serves one file per name forever, and the
engine pins its hash. Any change to what a package contains needs its `rev` bumped in
the same commit, in that package's `package.yml`. CI compares each rebuilt package against what is published and fails
if the contents moved without a rev bump.

Bumping a version usually means bumping `rev` back to 1, since the version already makes
the name unique.
