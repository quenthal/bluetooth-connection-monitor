# Publishing checklist

This repository is ready for GitHub and HACS custom-repository testing after one required edit.

## 1. Replace the repository owner placeholder

In:

```text
custom_components/bluetooth_connection_monitor/manifest.json
```

replace all occurrences of:

```text
YOUR_GITHUB_USERNAME
```

with your GitHub username or organization.

The expected repository name is:

```text
bluetooth_connection_monitor
```

If you choose a different repository name, update both URLs accordingly.

## 2. Create the GitHub repository

Recommended repository description:

> Exposes Home Assistant Bluetooth connection-slot allocations as automation-friendly binary sensors.

Recommended GitHub topics:

- home-assistant
- homeassistant
- hacs
- bluetooth
- esphome
- custom-component

Enable GitHub Issues.

## 3. Push the repository contents

The repository root should contain at least:

```text
custom_components/bluetooth_connection_monitor/
brand/icon.png
.github/workflows/validate.yml
README.md
LICENSE
hacs.json
```

## 4. Validate

The included GitHub workflow runs HACS repository validation on pushes, pull requests, a daily schedule, and manual dispatch.

## 5. Test through HACS

Add the repository to HACS as a custom repository with category **Integration**, install it, restart Home Assistant, and add the integration through **Settings → Devices & services**.

## 6. Optional release

HACS can install from the default branch without a release. For cleaner version selection, create a GitHub release tagged:

```text
v0.2.0
```
