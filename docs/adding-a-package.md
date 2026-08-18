# Adding or changing a package

The checkout is a Conan `local-recipes-index`. Each recipe directory needs Conan's
native version map and an ordinary recipe:

```text
recipes/libpng/config.yml
recipes/libpng/all/conanfile.py
recipes/libpng/all/conandata.yml
```

`config.yml` maps references exposed by the remote to their recipe folder:

```yaml
versions:
  "1.6.58":
    folder: all
```

The recipe remains the source of truth for building and consuming the binary. Use normal
Conan fields and methods rather than O3DE metadata:

- `validate()` rejects target configurations O3DE does not ship.
- `requirements()` and `tool_requires()` describe the complete dependency graph.
- `cpp_info` describes include paths, definitions, libraries, CMake package names and
  CMake target aliases.
- `upload_policy = "skip"` marks a build-only recipe that should not become an O3DE
  archive, such as `libclang`.

There is no catalog, `platforms`, `rev`, `payload`, or bundle declaration. Every host
dependency is deployed as an independent package under a payload directory matching its
Conan recipe name.

## Build it

After registering the checkout as the `o3de` remote, use standard Conan commands:

```bash
conan graph info --requires=libpng/1.6.58 \
    -pr:h=profiles/mac-arm -pr:b=profiles/mac-arm --update --filter=binary

conan install --requires=libpng/1.6.58 \
    -pr:h=profiles/mac-arm -pr:b=profiles/mac-arm \
    --update --build=missing \
    --output-folder=build/mac-arm --envs-generation=false \
    --deployer=extensions/deployers/engine_package.py \
    --deployer-folder=packages/mac-arm

python3 tools/validate_package.py packages/mac-arm
```

`conan graph info` reports `binary: Invalid` for a profile rejected by the recipe. CI
uses that as a skip rather than maintaining a second platform list.

`--update` is significant for a local recipes index: it refreshes cached recipe
revisions, including local dependencies that changed without a version bump.

## CMake information

The deployer generates `<name>-config.cmake` and a `Find<target>.cmake` shim from the
recipe's `cpp_info`. In particular:

```python
def package_info(self):
    self.cpp_info.set_property("cmake_file_name", "PNG")
    self.cpp_info.set_property("cmake_target_name", "PNG::PNG")
    self.cpp_info.includedirs = ["include"]
```

The engine-facing target is `3rdParty::PNG`; the upstream spelling `PNG::PNG` becomes an
alias. Dependencies are downloaded and linked through their own generated O3DE targets.

Some packages need CMake behavior that cannot be inferred from `cpp_info`, such as Qt's
MOC helpers or PySide's Python installation. Put those files in
`recipes/<name>/all/cmake/`. They are copied to the archive root and replace generated files
of the same name.

## Immutable publication

Do not bump a release counter. The deployer derives a SHA-256 deployment revision from
the resolved Conan binary and the complete O3DE package image. A change to the recipe,
binary, CMake integration, descriptor, or deployer produces a new package name while the
upstream version can remain unchanged. Package filenames use a 96-bit prefix of that
revision; `packages-manifest.json` retains the complete digest, and engine package pins
retain the complete archive SHA-256.
