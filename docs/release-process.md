# Releasing packages

## What a release is

A package is identified by `<name>-<version>-rev<rev>-<platform>` and is immutable once
published. Releasing means building packages, publishing them, and opening a pull
request against the engine that pins the new names and hashes.

Nothing is rebuilt between the development and production buckets. The bytes that CI
validated are the bytes that ship.

## The pipeline

1. **Build** (`.github/workflows/build.yml`) runs on every pull request that touches
   recipes, profiles, the consumer, the deployer, scripts or the lockfile. Each platform
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

## Bumping a package

Change `version` or `rev` in `recipes/<name>/package.yml` and open a pull request. That is the
whole procedure.

CI compares every rebuilt package against what is already published. If contents changed
but the name did not, the build fails and asks for a rev bump; if the package is
byte-identical to the published one, it is simply not republished.

## Secrets and variables

Inherited unchanged from the previous pipeline.

| Name | Kind | Purpose |
| --- | --- | --- |
| `AWS_CREDS_ACCESS_KEY`, `AWS_CREDS_SECRET_KEY`, `AWS_CREDS_REGION_NAME` | secret | S3 upload |
| `AWS_PACKAGE_DEV_S3_BUCKET`, `AWS_PACKAGE_PROD_S3_BUCKET` | secret | destination buckets |
| `GHA_TOKEN` | secret | opens the engine pull request |
| `PROD_CDN`, `DEV_CDN` | variable | CDN in front of each bucket |

## Checking packages before they ship

```bash
tools/3rdparty.py package mac-arm          # build and write packages/mac-arm
tools/3rdparty.py validate mac-arm         # shape, hashes, manifest, find_package
tools/engine_check.py packages/mac-arm --engine ../Engine
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
