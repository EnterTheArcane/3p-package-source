# Migration status

The old `package-system/` and `Scripts/` tree is gone; this describes what replaced it and
what is and is not yet proven.

## What the Conan build produces

Everything under `recipes/` builds, passes `validate_package.py`, and is resolved by the
engine's own package system through `engine_check.py`, with package hash and full content
validation forced on. Run `tools/3rdparty.py packages` for the current inventory.

O3DE `development` builds against the mac-arm set with nothing from the CDN: 34 pinned
packages, 32 of them unpacked and used by the build, and one engine source change (see
below). The other ten platforms have profiles, a lockfile and a resolving dependency
graph, and ios-arm builds and validates, but only mac-arm has been through an engine
build. The deleted tree remains in git history if a platform needs it as reference.

Every package is built from a recipe in this repository. Most were adapted from Conan
Center's, keeping upstream's build and replacing only the metadata the engine needs.
These are ours for a reason beyond that:

| Package | Why it needs a recipe |
| --- | --- |
| `lua` | Engine code includes `<Lua/lualib.h>`, and the sources are patched to compile out `os.execute` and friends on iOS and Android. Stock Lua does not build for iOS at all. |
| `xxhash` | Engine code includes `<xxhash/xxhash.h>`; Conan Center installs the header flat. |
| `mikktspace` | Engine code includes `<mikkelsen/mikktspace.h>`, after the author; Conan Center installs the header flat. |
| `glad` | Pre-generated loaders. Regenerating would change the exported symbol set. |
| `mcpp` | The O3DE fork adds C++ linkage and the include-report callback the shader builder uses. |
| `azslc` | O3DE's own shader compiler. |
| `dxc` | O3DE's DXC fork, which carries the `dxsc` tool. |
| `ispc-texcomp` | No Conan Center recipe; needs the ISPC compiler and a different patch on Apple Silicon. |
| `physx` | Ships four configurations side by side, which the engine selects between at consume time. |
| `nvcloth` | Conan Center builds the 1.1.6 release branch, where the callback interfaces are in `physx`; engine code derives from `nv::cloth::PxAssertHandler`, which only exists on master. Also ships one library per configuration. |
| `qt` | Conan Center has no 6.10.2 and packages Qt differently from what the engine's FindQt expects. |
| `python` | A relocatable framework build, not a normal Python. |
| `pyside` | Conan Center has no PySide recipe at all. |
| `libclang` | A build tool, never shipped: the libclang build the Qt project uses, replacing `brew install llvm@20`. Plain LLVM release binaries do not work; see the gotcha below. |

## Gotchas worth remembering

Things that cost real time to find, recorded so they do not have to be found twice.

- **PhysX writes arm64 libraries into `bin/mac.x86_64`.** The directory name is simply
  wrong upstream. It also compiles with `-Weverything -Werror` against a suppression list
  written years ago, so each new compiler release fails the build on a new warning;
  `-Werror` is switched off rather than chasing them.
- **Directory symlinks must be materialised, file symlinks must not.** macOS frameworks
  are built out of directory links, and the engine receives them as real directories
  holding a second copy. Getting this wrong ships a Qt with no headers.
- **`/var` is a symlink to `/private/var` on macOS.** O3DE's Qt patch calls
  `get_filename_component(REALPATH)`, so a build or probe under a symlinked path hands
  CMake a directory it does not recognise. Both tools now resolve their temp paths.
- **Qt and Python configs need `PAL_PLATFORM_NAME`**, which only the engine defines. Both
  now derive it when absent so the packages resolve standalone.
- **Some libraries are more than one library.** OpenImageIO splits its symbols between
  OpenImageIO and OpenImageIO_Util, and `ImageSpec`'s inline destructor calls into the
  second, so linking only the first leaves a consumer with undefined symbols that read
  as if the package were broken. Freetype is the mirror image: it calls into libpng, so
  a package built with PNG support cannot be linked by a target that takes Freetype
  alone. Both were found by the engine link, not by anything we generate.
- **A lockfile pins local recipes too.** Editing one produces a new recipe revision, and
  the lockfile keeps resolving the revision from before the edit, so the build runs the
  old recipe and the change looks like it did nothing. `3rdparty.py export` now moves
  those entries forward; Conan Center entries stay pinned, which is the point of the file.
- **NvCloth's compiler flags are dead code.** Its mac cmake chooses architecture with
  `IF (DEFINED PX_32BIT) ... ELSEIF() ... ENDIF()`, and an `ELSEIF()` with no condition is
  never true, so neither branch runs and `CMAKE_CXX_FLAGS` stays empty. The previous build
  had the same dead branch, so it too was built without NvCloth's intended flags. It does
  mean nothing overwrites what the recipe passes on the command line.
- **A profile's `[conf]` is not part of a package id.** Edit one and the cached binary
  still looks current, so `--build=missing` reuses it and the change silently does
  nothing. `tools/3rdparty.py --rebuild` forces the build; CI keeps the profile hash in
  its own cache key segment so `restore-keys` cannot serve a stale binary either.
- **`--only` still builds and deploys the whole dependency graph.** Options therefore go
  on for every catalog entry, not just the selected one: scoped to the selection alone,
  building one package republishes its dependencies with their recipe defaults and
  quietly undoes an earlier full build.
- **Shiboken needs the libclang Qt publishes, not LLVM's own release binaries.** With
  LLVM's, it resolves `QDirListing::IteratorFlag` onto `QDirIterator`'s enum and emits
  wrappers referencing a `Default` member that does not exist. What was actually
  measured: Qt's 20.1.3 works, LLVM's 20.1.8 and 22.1.8 both fail that way. That leaves
  Qt's patches and an upstream change after 20.1.3 as competing explanations -- building
  against LLVM's own 20.1.3 would separate them, and has not been done.
- **A buildenv only reaches `self.run` when env scripts are generated.** Packaging turns
  that off, so a `tool_requires` that exports variables silently contributes nothing and
  the build picks up whatever the machine has. PySide passes libclang's path explicitly
  for exactly this reason.
- **A framework Python does not look like a unix Python.** PySide's `setup.py` needs
  `libpython` and the headers linked into the virtual environment, and shiboken's
  libclang needs `SDKROOT` or it cannot find `<type_traits>`.

## Where package metadata lives

In the recipe. `version`, `rev` and `platforms` are class attributes, read out of the
source without running it, because the consumer has to know which packages a platform
wants before Conan has a graph to ask. Conan's own `conan inspect` reports only the
attributes it knows about, so it cannot carry these.

Everything else comes from the resolved conanfile at deploy time: the engine's target
name from `cmake_file_name`, and `payload`, `bundle`, `bundle_targets`, `includedirs`
and `defines` as class attributes. A recipe without `platforms` is a build tool that is
never shipped, which is what `libclang` is.

Bumping `rev` changes the recipe revision and so rebuilds the package. That costs
nothing in practice: `rev` is bumped when the contents changed, which already required
a rebuild.

## What was deleted

`package-system/`, `Scripts/`, the five `package_build_list_host_*.json` files,
`package.sh`, `package.bat`, the `SPDX-Licenses` files, and the three workflows that drove
them. Everything the recipes still need was vendored first: ten patches under
`recipes/*/patches/` and ten curated cmake files under `recipes/*/cmake/`, all of which
build without reference to the deleted tree.

It stays in git history. The recipes for the platforms that have not been built yet were
transposed from those scripts, and `git show` on an earlier commit is the reference if a
platform turns out to need something that was not carried across.

## Engine source changes these packages require

Version moves that the engine's own code has to catch up with. They belong in the same
pull request that repoints the package names, not here.

| Change | Why |
| --- | --- |
| `Gems/GradientSignal/Code/Tests/EditorGradientSignalBakerTests.cpp` -- `read_image(OIIO::TypeDesc::FLOAT, data)` becomes `read_image(0, 0, 0, spec.nchannels, OIIO::TypeDesc::FLOAT, data)` | OpenImageIO 3.x dropped the overload that read every channel implicitly. One call site. |

Deliberately not taken: moving benchmark past 1.7.1, which would need roughly 635 call
sites updated across 31 files. See the deviations below.

## Known deviations from the old builds

- **asn1** is not ported. It was listed only for iOS, its directory never existed in the
  repository, and nothing in the engine consumes it.
- **PhysX 4** is not ported; it is deprecated in favour of PhysX 5.
- **The AWS packages** are dropped.
- **Versions** track the latest on Conan Center, except where the engine depends on a
  particular API: Lua stays on 5.4, pybind11 on 2.x, and OpenSSL on 3.6.3 rather than
  4.x. OpenSSL moving from 1.1.1 to 3.x is the largest engine-visible change.
- **benchmark stays on 1.7.1**, the newest release the engine's own source compiles
  against. 1.9 deprecates the const-ref `DoNotOptimize` overload and the global
  `Benchmark` type, and the engine builds its tests with `-Werror`: 31 files and roughly
  635 call sites would have to be updated first. That is an engine change, and until it
  happens a 1.9 package is not a drop-in replacement.
- **freetype** is redirected from `zlib-ng` back to `zlib`; see `profiles/_common`. It is
  also built without PNG, as the previous package was: the engine links Freetype on its
  own, so a Freetype that calls into libpng cannot be linked at all.
- **DXC** stays on the O3DE fork. Of its eight commits, four are cherry picks now upstream,
  but `dxsc`, the SPIR-V invariant decoration and `-fvk-disable-depth-hint` are not.
  Rebasing the fork onto a newer upstream would drop the redundant four and get a newer
  LLVM; `dxsc` is what prevents dropping the fork entirely.
