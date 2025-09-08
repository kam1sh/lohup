# Lohup

(_loh-up - backup for lohs[1]_)

Lohup - backups done dummy.

## Development status

Early alpha. Works on my machines.

## Installation

[Restic](https://restic.net) and [uv](https://docs.astral.sh/uv/) for Python required. Or just Python 3.13 and restic.

```bash
apt update && apt install -y restic
uv tool install git+https://github.com/kam1sh/lohup
```

## Usage

Example configuration see in [corresponding directory](examples/complete.toml)

CLI examples:

```bash
lohup --config config.toml restic --repo cloud -- init
# if config=lohup.toml then option can be omitted
lohup backup-all
lohup snapshots --repo cloud
```

## Core features

* Configuration in TOML
* Restic as a backup driver
* Backup hooks, such as create/remove btrfs filesystem snapshot
* Environment variables

### Features in TODO

* LVM hooks
* Better error handling and printing
* Verbose/debug messages
* Metrics and OpenTelemetry support
* Binary releases, win+linux amd64 along with Python wheel
* Include files in profiles with `paths-from` 

## Development

```bash
git clone git@github.com:kam1sh/lohup lohup-dev && cd lohup-dev
# install dependencies
uv sync --group dev
# run tests
uv run pytest --tb=short
# building binaries to dist directory
uv run pyinstaller -F lohup-cli.spec
```

[1] in my native language loh (лох) means "dummy" or "looser"
