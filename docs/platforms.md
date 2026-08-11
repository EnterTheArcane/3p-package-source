# Target platforms

Every target has a profile in `profiles/`. The profile name is the platform id: it
is also the suffix of every package built for that target, so `profiles/mac-arm`
produces `zlib-1.3.1-rev1-mac-arm`. `tools/catalog.py` derives the same id from
Conan settings, which keeps profiles, package names and the deployer in agreement
without a translation table.

Architecture is always explicit. There is no unsuffixed profile that quietly means
x64.

| Platform id | Target | Built on |
| --- | --- | --- |
| `windows-x64` | Windows x64 | `windows-2025` |
| `windows-arm` | Windows ARM64 | `windows-2025` (cross) |
| `linux-x64` | Linux x64 | `ubuntu-24.04` |
| `linux-arm` | Linux ARM64 | `ubuntu-24.04` (cross) |
| `mac-x64` | Mac x64 | `macos-26` (cross) |
| `mac-arm` | Mac ARM64 | `macos-26` |
| `android-arm` | Android ARM64 | `ubuntu-24.04` (cross) |
| `android-x64` | Android x64 | `ubuntu-24.04` (cross) |
| `ios-arm` | iOS device | `macos-26` (cross) |
| `ios-simulator` | iOS simulator, ARM64 | `macos-26` (cross) |
| `emscripten` | WebAssembly | `ubuntu-24.04` (cross) |

Everything cross compiles from one of three runner images. Android no longer needs
a Windows host, and iOS no longer needs an Intel Mac, because the NDK and the SDKs
come from Conan or from the runner image rather than from whatever the machine
happened to have installed.

## Shared settings

`profiles/_common` holds what every target agrees on: release builds, C++20, Ninja.
Each platform profile includes it and adds its own toolchain.

`compiler.cppstd` is repeated in each platform profile rather than living in
`_common`. A subsetting cannot be set before the compiler it belongs to is defined,
and the including profile is what defines the compiler, so hoisting it fails with
`'settings.compiler' value not defined`.

`_common` also exports `CMAKE_POLICY_VERSION_MINIMUM=3.5`. CMake 4 refuses to configure
a project whose `cmake_minimum_required` is below 3.5, which several small, long stable
libraries still declare. Setting it here keeps those buildable without forking their
recipes; dropping the shim means forking each one.

## Always pass both profiles

Conan falls back to the user's default profile for anything not specified. A default
profile can carry settings, and even `[replace_requires]` rules that silently swap
one library for another, which would end up baked into a shipped package.
The commands therefore always pass `-pr:h` and `-pr:b` explicitly, using
the profile for the machine it is running on as the build profile. Do the same when
invoking Conan by hand.

## Toolchains from Conan

`android-arm`, `android-x64` and `emscripten` pull their toolchain through
`[tool_requires]` (`android-ndk`, `emsdk`). A tool required this way applies to every
package in the graph, including the tool's own dependencies, which makes the tool
require itself. The profiles exclude that subtree:

```
[tool_requires]
!(emsdk/*|nodejs/*): emsdk/3.1.73
```

Without the exclusion the graph fails to resolve with a cycle. If a tool gains a new
dependency, add it to the exclusion list.
