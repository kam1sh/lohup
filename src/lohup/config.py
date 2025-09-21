import platform
import tomllib
from pathlib import Path
from dataclasses import dataclass

from lohup.util import catch_errors, ensure_exists, CatcherError, Masked
from lohup.expander import VarExpander
from lohup.logger import LogLevel


class ConfigError(ValueError):
    pass


@dataclass
class Settings:
    backup_base_dir: Path
    globalvars: dict[str, str]
    build_dir: Path
    subsystem: str

    @staticmethod
    def load(conf: dict):
        with catch_errors() as catch:
            basedir = conf.get("backup-base-dir")
            basepath = Path(basedir) if basedir else Path.cwd()
            tmpdir = conf.get("tmp-dir")
            tmp_path = Path("/tmp/lohup")
            if not tmpdir:
                if platform.system() == "Windows":
                    tmp_path = Path.home().joinpath("AppData", "Local", "Temp", "lohup")
            else:
                tmp_path = Path(tmpdir)
            settings = Settings(
                backup_base_dir=basepath,
                globalvars=conf.get("globalvars") or {},
                build_dir=tmp_path,
                subsystem=conf.get("subsystem-name", "restic"),
            )
            settings.globalvars["BDIR"] = str(basepath)
            settings.globalvars["BUILDDIR"] = str(settings.build_dir)
            for key, value in settings.globalvars.items():
                if "$" in value:
                    catch.error(
                        f"variable {key!r}: nested references in globals are not allowed"
                    )
        return settings


@dataclass
class LocalRepository:
    name: str
    path: str
    repo_key_file: Masked
    default: bool

    @staticmethod
    def load(name: str, conf: dict, expander: VarExpander):
        with catch_errors() as catcher:
            repo = LocalRepository(
                name=name,
                path=expander.expand(conf.get("path")),
                repo_key_file=Masked(expander.expand(conf.get("repo-key-file", ""))),
                default=conf.get("default", False),
            )
            if not repo.path:
                catcher.error("field 'path' not set")
            if msg := ensure_exists(repo.repo_key_file, field="repo-key-file"):
                catcher.error(msg)
        return repo


@dataclass
class S3Repository:
    name: str
    endpoint: str
    region: str
    access_key_file: Masked
    secret_key_file: Masked
    repo_key_file: Masked
    bucket: str
    path: str
    default: bool

    @staticmethod
    def load(name: str, conf: dict, expander: VarExpander):
        repo = S3Repository(
            name=name,
            endpoint=expander.expand(conf.get("endpoint", "https://s3.amazonaws.com")),
            region=conf.get("region", ""),
            access_key_file=Masked(expander.expand(conf.get("access-key-file", ""))),
            secret_key_file=Masked(expander.expand(conf.get("secret-key-file", ""))),
            repo_key_file=Masked(expander.expand(conf.get("repo-key-file", ""))),
            bucket=expander.expand(conf.get("bucket", "")),
            path=expander.expand(conf.get("path", "/")),
            default=conf.get("default", False),
        )
        with catch_errors() as catcher:
            if not repo.endpoint:
                catcher.error("field 'endpoint': not set")
            if not repo.bucket:
                catcher.error("field 'bucket': not set")
            if value := repo.access_key_file.value:
                if msg := ensure_exists(value, field="access-key-file"):
                    catcher.error(msg)
            if value := repo.secret_key_file.value:
                if msg := ensure_exists(value, field="secret-key-file"):
                    catcher.error(msg)
            if msg := ensure_exists(repo.repo_key_file, field="repo-key-file"):
                catcher.error(msg)
        return repo


Repository = LocalRepository | S3Repository


@dataclass
class CommandHook:
    command: str
    hook_kind: str

    def load(conf: dict, kind: str, expander: VarExpander):
        return CommandHook(command=expander.expand(conf.get("command")), hook_kind=kind)


@dataclass
class BtrfsHook:
    action: str
    subvolume: str
    snapshot: str | None
    hook_kind: str

    @staticmethod
    def load(conf: dict, kind: str, expander: VarExpander):
        return BtrfsHook(
            action=conf.get("action"),
            subvolume=expander.expand(conf.get("subvolume")),
            snapshot=expander.expand(conf.get("snapshot")),
            hook_kind=kind,
        )


Hook = CommandHook | BtrfsHook


@dataclass
class HookSet:
    before_all: list[Hook]
    after_all: list[Hook]

    @staticmethod
    def load(conf: dict, expander: VarExpander):
        with catch_errors() as catcher:
            before_all = []
            after_all = []
            for hook in conf.get("before-all", []):
                match kind := hook.get("kind"):
                    case "command":
                        catcher.catch(
                            lambda: before_all.append(
                                CommandHook.load(hook, kind=kind, expander=expander)
                            ),
                            prefix="before-all command:",
                        )
                    case "btrfs":
                        catcher.catch(
                            lambda: before_all.append(
                                BtrfsHook.load(hook, kind=kind, expander=expander)
                            ),
                            prefix="before-all btrfs:",
                        )
                    case _:
                        catcher.error(f"Unsupported before-all: {kind}")
            for hook in conf.get("after-all", []):
                match kind := hook.get("kind"):
                    case "command":
                        catcher.catch(
                            lambda: after_all.append(
                                CommandHook.load(hook, kind=kind, expander=expander)
                            ),
                            prefix="after-all command:",
                        )
                    case "btrfs":
                        catcher.catch(
                            lambda: after_all.append(
                                BtrfsHook.load(hook, kind=kind, expander=expander)
                            ),
                            prefix="after-all btrfs:",
                        )
                    case _:
                        catcher.error(f"after-all: unknown kind {kind!r}")
            return HookSet(before_all=before_all, after_all=after_all)


@dataclass
class PathsProfile:
    name: str
    repo: str | None
    paths: list[str]
    exclude_paths: list[str]
    cli_args: list[str]


@dataclass
class CommandProfile:
    name: str
    repo: str | None
    command: str | list[str]
    cli_args: list[str]


Profile = PathsProfile | CommandProfile


@dataclass
class TomlConfig:
    settings: Settings
    repos: dict[str, Repository]
    hooks: HookSet
    expander: VarExpander
    profiles: dict[str, Profile]

    @staticmethod
    def from_file(name: str, logger):
        path = Path(name)
        try:
            with catch_errors(failfast=logger.accepts(LogLevel.VERBOSE)) as catcher:
                return TomlConfig._ffile_impl(name, path, catcher)
        except CatcherError as e:
            raise ConfigError("Failed to parse TOML config") from e

    @staticmethod
    def _ffile_impl(name: str, path: Path, catcher):
        if not path.exists():
            catcher.error(f"Config {name!r} does not exist")
            return
        with path.open("rb") as fp:
            conf: dict = tomllib.load(fp)
        settings = Settings.load({})
        if value := conf.get("settings"):
            settings = catcher.catch(lambda: Settings.load(value), prefix="settings:")
            if not settings:
                return
        expander = VarExpander.from_conf(settings)
        repos = {}
        for name, opts in conf.get("repos", {}).items():
            error_prefix = f"repo {name!r}:"
            match kind := opts.get("kind"):
                case "s3":
                    repos[name] = catcher.catch(
                        lambda: S3Repository.load(name, opts, expander=expander),
                        prefix=error_prefix,
                    )
                case "local":
                    repos[name] = catcher.catch(
                        lambda: LocalRepository.load(name, opts, expander=expander),
                        prefix=error_prefix,
                    )
                case None:
                    catcher.error(f"{error_prefix} repository type not set")
                case _:
                    catcher.error(f"{error_prefix} unsupported kind: {kind}")
        if not repos:
            catcher.error("no repositories defined")
        hooks = None
        if hook_conf := conf.get("hooks"):
            hooks = catcher.catch(
                lambda: HookSet.load(hook_conf, expander=expander), prefix="hook:"
            )
        profiles = {}
        for name, opts in conf.get("profiles", {}).items():
            args = opts.get("cli-args", [])
            if cmd := opts.get("command"):
                profiles[name] = CommandProfile(
                    name, repo=opts.get("repo"), command=cmd, cli_args=args
                )
            else:
                paths = opts.get("paths")
                if not paths:
                    catcher.error(f"profile {name!r}: no paths or command provided")
                    continue
                profiles[name] = PathsProfile(
                    name,
                    repo=opts.get("repo"),
                    paths=[expander.expand(x) for x in paths],
                    exclude_paths=[
                        expander.expand(x) for x in opts.get("exclude-paths", [])
                    ],
                    cli_args=args,
                )
        toml = TomlConfig(
            settings=settings,
            repos=repos,
            hooks=hooks,
            expander=expander,
            profiles=profiles,
        )
        return toml
