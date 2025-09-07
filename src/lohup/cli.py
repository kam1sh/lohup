import click
import humanize
from datetime import datetime

from lohup.app import Lohup
from lohup import logger
from lohup.config import ConfigError


@click.group()
@click.option("--config", envvar="LOHUP_CONFIG", default="lohup.toml")
@click.pass_context
def cli(ctx, config):
    log = logger.CliLogger(level=logger.LogLevel.DEBUG)
    ctx.obj = Lohup(config_path=config, logger=log)
    try:
        ctx.obj.load()
    except ConfigError as e:
        log.error(e)
        raise click.Abort()


@cli.command()
@click.option("--repo", help="Lohup repository name", required=True)
@click.argument("args", nargs=-1)
@click.pass_obj
def restic(obj: Lohup, repo, args: tuple[str, ...]):
    """
    Pass command to restic
    """
    obj.invoke_restic(repo, args)


@cli.command()
@click.argument("profile", required=True, nargs=1)
@click.pass_obj
def backup(obj: Lohup, profile: str):
    obj.backup(profile=profile)


@cli.command()
@click.pass_obj
def backup_all(obj: Lohup):
    obj.backup_all()


@cli.command()
@click.option("--repo", help="Lohup repository name", required=True)
@click.option("--raw", "raw_mode", is_flag=True)
@click.pass_obj
def snapshots(obj: Lohup, repo: str, raw_mode: bool):
    result = obj.snapshots(repo=repo, is_json=not raw_mode)
    if raw_mode:
        return click.echo(result, nl=False)
    # time, parent?, tree, paths, hostname, uid, gid
    # tags, version, summary, id, short_id
    snapshots = []
    for snap in result:
        name = "-".join(snap["tags"])
        dt = datetime.fromisoformat(snap["time"])
        delta = humanize.naturaltime(datetime.now())
        summary = snap["summary"]
        end = datetime.fromisoformat(summary["backup_end"])
        changes = summary["files_new"] + summary["files_changed"]
        snapshots.append(
            dict(
                id=snap["short_id"],
                name=name,
                when_started=dt,
                started_human=delta,
                hostname=snap["hostname"],
                duration=end - dt,
                changes=changes,
                changes_ratio=changes / summary["total_files_processed"],
                size_comp=summary["data_added_packed"],
                size_raw=summary["data_added"],
                processed=summary["total_bytes_processed"],
            )
        )
    snapshots.sort(key=lambda x: x["when_started"])
    for snap in snapshots:
        name = click.style(snap["name"], fg="blue", italic=True)
        click.echo(f"Snapshot {snap['id']} ({name}):")
        started = humanize.naturaltime(snap["when_started"])
        text = click.style(started, fg="blue")
        took = humanize.naturaldelta(snap["duration"])
        click.echo(f"\tStarted: {text} (took {took})")
        ratio = snap["changes_ratio"] * 100
        ratio = click.style(f"{ratio:.1f}%", fg="blue")
        click.echo(f"\tFiles changed (since previous): {snap['changes']} ({ratio})")
        size = humanize.naturalsize(snap["size_raw"], binary=True)
        compressed = humanize.naturalsize(snap["size_comp"], binary=True)
        ratio = snap["size_raw"] / snap["processed"]
        ratio = click.style(f"{ratio:.1f}%", fg="blue")
        click.echo(f"\tDiff size: {compressed}, unpacked: {size} ({ratio})")
        click.echo(f"\tHost: {snap['hostname']}")
        click.echo()


if __name__ == "__main__":
    cli()
