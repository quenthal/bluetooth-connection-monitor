# Publishing checklist

This repository is configured for:

```text
https://github.com/quenthal/bluetooth-connection-monitor
```

## 1. Repository settings

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

## 2. Repository structure

The repository root should contain at least:

```text
custom_components/bluetooth_connection_monitor/
custom_components/bluetooth_connection_monitor/brand/icon.png
.github/workflows/validate.yml
README.md
LICENSE
hacs.json
```

## 3. Validate

The included GitHub workflow runs HACS repository validation plus Python and JSON checks.

## 4. Test through HACS

Add the repository to HACS as a custom repository with category **Integration**, install it, restart Home Assistant, and add the integration through **Settings → Devices & services**.

## 5. Release

Create a GitHub release tagged:

```text
v0.3.0
```

Use the same version in `manifest.json`.
