# Target platforms

Each target is a normal Conan host profile. The build profile is the native profile of
the CI runner; Android, iOS, Emscripten and non-native architectures cross-compile.

| Profile | Conan host | CI runner |
| --- | --- | --- |
| `windows-x64` | Windows x86-64 | Windows x86-64 |
| `windows-arm` | Windows ARM64 | Windows x86-64 |
| `linux-x64` | Linux x86-64 | Linux x86-64 |
| `linux-arm` | Linux ARM64 | Linux x86-64 |
| `mac-arm` | macOS ARM64 | macOS ARM64 |
| `android-arm` | Android ARM64 | Linux x86-64 |
| `android-x64` | Android x86-64 | Linux x86-64 |
| `ios-arm` | iOS device ARM64 | macOS ARM64 |
| `ios-simulator` | iOS simulator ARM64 | macOS ARM64 |
| `emscripten` | WebAssembly | Linux x86-64 |

Every profile defines `user.o3de:platform`. The deployer uses that canonical O3DE value
in the manifest and immutable package name; compiler, OS, architecture, options and tool
requirements remain normal Conan profile data.

Package applicability is not stored in a parallel platform catalog. A recipe rejects an
unsupported O3DE configuration with `ConanInvalidConfiguration` from `validate()`.
Conan evaluates this after graph construction, so use `conan graph info --filter=binary`
to preflight a matrix entry. An invalid result is a CI skip; other graph errors remain
failures.

For example:

```bash
conan graph info --requires=qt/6.10.2 \
    -pr:h=profiles/android-arm -pr:b=profiles/linux-x64 \
    --update --filter=binary
```
