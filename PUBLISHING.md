# Publishing checklist

Repository:

```text
https://github.com/quenthal/bluetooth-connection-monitor
```

## Versioning

Use calendar versioning:

```text
YYYY.M.PATCH
```

Examples:

- `2026.8.0` - first August 2026 release
- `2026.8.1` - first patch release in August 2026
- `2026.9.0` - first September 2026 release

The version in `custom_components/bluetooth_connection_monitor/manifest.json` and the GitHub Release tag must match, except that the tag is prefixed with `v`.

Example:

```text
manifest.json: 2026.8.0
GitHub tag:     v2026.8.0
```

Do not use the Home Assistant version as a compatibility claim. Calendar versioning here describes when Bluetooth Connection Monitor itself was released.

## Release workflow

1. Make changes in a branch and run the tests and Ruff locally (see *Development* in `README.md`).
2. Update the version in `custom_components/bluetooth_connection_monitor/manifest.json`.
3. Update `CHANGELOG.md`; list breaking changes separately.
4. If the minimum Home Assistant version changes, update `hacs.json`, `README.md` and the minimum version in the test matrix of `.github/workflows/validate.yml`.
5. Open a pull request, wait for GitHub Actions to pass and merge it to `main`.
6. Create a full GitHub Release (a tag alone is not enough for HACS release versioning).
7. Tag the release with the matching `vYYYY.M.PATCH` version.
8. In HACS, refresh/re-download as needed and verify the published version.

Once GitHub Releases are used, HACS uses the latest release tag as the remote version. Without releases, HACS falls back to the first seven characters of the latest commit hash.

## Repository settings

Recommended description:

> Expose Home Assistant Bluetooth connection allocations as automation-friendly binary sensors.

Recommended GitHub topics:

- home-assistant
- homeassistant
- hacs
- bluetooth
- esphome
- custom-component

Enable GitHub Issues.

## Validation

The included GitHub workflow runs:

- HACS validation
- Hassfest validation
- Ruff lint and format check
- JSON validation
- Tests against the minimum supported and the latest Home Assistant version

For a future submission to the default HACS repository, publish a full GitHub Release only after the validation actions pass.
