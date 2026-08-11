# Adding or changing a package

Every package is a directory under `recipes/` holding a `conanfile.py` we own. Most were
adapted from Conan Center's recipe, keeping upstream's build and adding the few things the
engine needs on top. Run `conan 3p:packages` for the whole inventory in one view.

## What a recipe declares for us

Three class attributes, written directly under `version`:

```python
class LibPngConan(ConanFile):
    name = "libpng"
    version = "1.6.58"
    rev = 1
    platforms = "core"
    aliases = {"PNG": ["PNG::PNG"]}
```

- `rev` is the release counter. The package is named `libpng-1.6.58-rev1-mac-arm`.
- `platforms` selects where it is built: one of `all`, `core`, `desktop`, `tools`,
  `mobile`, `windows`, `web`, or a list of platform ids. A recipe with no `platforms` is a
  build tool that never ships, which is what `libclang` is.
- `aliases` adds the upstream target spelling, so a dependency doing `find_package(PNG)`
  links ours instead of a system copy.

These are read out of the recipe source without running it, because the consumer has to
know which packages a platform wants before Conan has a graph to ask. That means they have
to be plain literals -- `platforms = "core"`, not `platforms = SOME_GROUP`. Writing one any
other way is an error naming the file, not a package that quietly disappears.

The name the engine calls `find_package` with comes from `package_info()`:

```python
    def package_info(self):
        self.cpp_info.set_property("cmake_file_name", "PNG")
```

That is the same fact CMake already needs, so nothing is repeated. A recipe that omits it
fails at deploy time rather than guessing.

Then build and check it:

```bash
conan 3p:package mac-arm --only libpng
conan 3p:validate mac-arm
python3 tools/engine_check.py packages/mac-arm --engine ../Engine
```

## Starting from Conan Center's recipe

For anything Conan Center already builds well, copy its recipe rather than writing a build:

```bash
conan 3p:export                       # so the reference resolves
conan cache path libpng/1.6.58        # find the cached export
```

Copy `conanfile.py`, `conandata.yml` and any exported sources into `recipes/<name>/`, then
add the attributes above and set `cmake_file_name`. Two things to watch:

- Copy exported sources to where the *recipe* looks for them, not where they land after
  export. A recipe doing `copy(self, "x.cmake", self.recipe_folder, ...)` wants `x.cmake`
  beside the conanfile; the cache holds it already moved.
- Conan Center recipes enable every backend they support. Trim them in `default_options`.

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

Other class attributes the deployer reads: `payload` when the payload directory should not
be named after the recipe (`"."` puts it at the package root, which is how Python's
framework has to arrive), `includedirs` and `defines` for what the engine expects but the
recipe does not describe, and `bundle` below.

## Every dependency has to be accounted for

Conan resolves a package's dependencies for the build, but the engine only ever sees the
packages we publish. Anything a package depends on and we do not ship has to either go
away or come along, or the engine fails much later and somewhere confusing: a missing
archive shows up as undefined symbols at link time, and a missing header shows up as a
compile error inside one of our own headers.

Prefer turning it off. Most libraries make their format and codec backends optional --
libtiff builds against nothing but zlib once its codecs are off, which is what the engine
has always shipped.

Bundle what cannot be turned off. `bundle` names dependencies whose payload is merged into
this package: OpenEXR carries Imath, libdeflate and openjph that way, and OpenImageIO
carries fmt and Imath because its public headers include them by name. Bundle only what
the package actually requires -- a name the graph does not offer is an error, deliberately,
because a bundle that silently resolves to nothing ships a package that cannot be linked.

`bundle_targets` names which of those stay visible as engine targets. Only OpenEXR uses it,
for Imath; everything else bundled is implementation detail.

To find these before the engine does: `conan 3p:validate` fails a package whose binaries
load anything from outside the package, which also catches a dependency picked up from the
build machine rather than from us.

## Changing a package that is already published

Published packages are immutable: the CDN serves one file per name forever, and the
engine pins its hash. Any change to what a package contains needs its `rev` bumped in
the same commit. CI compares each rebuilt package against what is published and fails
if the contents moved without a rev bump.

Bumping a version usually means setting `rev` back to 1, since the version already makes
the name unique.
