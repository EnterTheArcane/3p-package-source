# Releasing packages

## What a release is

A package is identified by `<name>-<version>-<o3de-platform>-<deployment-id>` and is
immutable once published. The deployment ID is the first 24 hexadecimal characters
(96 bits) of the complete deployment SHA-256 recorded in `packages-manifest.json`.
Releasing means building packages, publishing them, and opening a pull request against
the engine that pins the new names and full archive hashes.

Nothing is rebuilt between the development and production buckets. The bytes that CI
validated are the bytes that ship.

## The pipeline

1. **Build** (`.github/workflows/build.yml`) runs on every pull request that touches
   recipes, profiles, the deployer, scripts or workflows. Each platform
   builds, validates and uploads its packages as an artifact.

   Conan decides what to rebuild. With the cache restored, a package whose recipe and
   dependencies have not changed is reused. There is no list of package names to edit to
   trigger a build.

2. **Promote** (`.github/workflows/promote.yml`) downloads those artifacts, validates
   them again, uploads them to the development bucket, opens a draft pull request against
   `o3de/o3de` with regenerated `BuiltInPackages_*.cmake` files, and then copies the same
   objects to the production bucket.

3. **The engine pull request** is where the change actually lands for users. Review it
   like any other engine change: a version bump can require code changes on the engine
   side, and this is where that surfaces.

## Changing a package

Change the recipe and open a pull request. Change its version and matching `config.yml`
entry when the upstream version changes; keep the version when only the build or O3DE
integration changes.

The deployment digest changes whenever the Conan binary or O3DE package image changes,
so a changed artifact receives a fresh CDN name automatically. Identical inputs reproduce
the same name and archive.

## Secrets and variables

Inherited unchanged from the previous pipeline.

| Name | Kind | Purpose |
| --- | --- | --- |
| `AWS_CREDS_ACCESS_KEY`, `AWS_CREDS_SECRET_KEY`, `AWS_CREDS_REGION_NAME` | secret | S3 upload |
| `AWS_PACKAGE_DEV_S3_BUCKET`, `AWS_PACKAGE_PROD_S3_BUCKET` | secret | destination buckets |
| `GHA_TOKEN` | secret | opens the engine pull request |
| `DEV_CDN` | variable | CDN in front of the development bucket |

## Checking packages before they ship

```bash
conan install --requires=zlib/1.3.1 \
    -pr:h=profiles/mac-arm -pr:b=profiles/mac-arm --update --build=missing \
    --deployer=extensions/deployers/engine_package.py \
    --deployer-folder=packages/mac-arm
python3 tools/validate_package.py packages/mac-arm
python3 tools/engine_check.py packages/mac-arm --engine ../o3de
```

`engine_check.py` is the strongest check available without configuring the whole engine:
it runs the engine's own package system against the built packages, with hash and full
content validation forced on, and resolves every declared target.

To point a real engine build at locally built packages instead of the CDN:

```bash
export LY_PACKAGE_SERVER_URLS="file:///path/to/3PS/packages/mac-arm"
```

The variable is additive and takes priority, so the engine finds local packages first
and falls back to the CDN for everything else.
