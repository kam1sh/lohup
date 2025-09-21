import subprocess as procs

from lohup import config
from lohup.logger import BasicLogger, LogLevel, LoggerProto
from lohup.restic import Restic
from lohup.rustic import Rustic


class Lohup:
    def __init__(self, config_path: str | None, logger: LoggerProto = None):
        self._config_path = config_path or "lohup.toml"
        self.config = None
        self.subsystem = None
        self.log = logger or BasicLogger(level=LogLevel.INFO)

    def load(self):
        self.config = config.TomlConfig.from_file(self._config_path, logger=self.log)
        self.subsystem = self.config.settings.subsystem
        if self.subsystem not in ("restic", "rustic"):
            raise KeyError(f"Invalid subsystem: {self.subsystem}")

    def invoke_direct(self, repo: str, args: tuple[str, ...]):
        spec = self.config.repos.get(repo) if repo else self._default_repo
        if spec is None:
            raise KeyError(f"Unknown repo: {repo}")
        engine = self._engine_for(spec)
        with engine:
            engine.run(args)

    def _exechooks(self, hooks: list):
        for h in hooks:
            match h:
                case config.BtrfsHook():
                    self._btrfs(h)
                case config.CommandHook():
                    procs.check_call(h.command.split())

    @staticmethod
    def _btrfs(spec: config.BtrfsHook):
        cmd = ["btrfs"]
        if spec.action == "snapshot":
            cmd += ["subvolume", "snapshot", spec.subvolume, spec.snapshot]
        elif spec.action == "delete":
            cmd += ["subvolume", "delete", spec.subvolume]
        else:
            raise ValueError(f"Unknown btrfs action: {spec.action}")
        procs.check_call(cmd)

    @property
    def _default_repo(self):
        default_list = list(filter(lambda x: x.default, self.config.repos.values()))
        return default_list.pop() if default_list else None

    def _repo_for(self, profile: config.Profile):
        default = self._default_repo
        if profile.repo is not None:
            if repo := self.config.repos.get(profile.repo):
                return repo
            else:
                raise KeyError(f"No repo attached to profile: {profile.name!r}")
        if default is None:
            raise KeyError(f"No repo attached to profile: {profile.name!r}")
        return default

    def _engine_for(self, repo: config.Repository):
        match self.subsystem:
            case "rustic":
                return Rustic(
                    repo, log=self.log, conf_dir=self.config.settings.build_dir
                )
            case "restic":
                return Restic(repo, log=self.log)
            case x:
                raise KeyError(f"Unknown subsystem: {x}")

    def backup(self, profile: str):
        spec = self._profile_for(profile)
        repo = self._repo_for(spec)
        engine = self._engine_for(repo)
        self._exechooks(self.config.hooks.before_all)
        try:
            self._invoke_profile(engine, profile=spec)
        finally:
            self._exechooks(self.config.hooks.after_all)
        self.log.info("Finished!")

    def backup_all(self):
        engines = {}
        for name, spec in self.config.profiles.items():
            engine = self._engine_for(self._repo_for(spec))
            engines[name] = engine
        self._exechooks(self.config.hooks.before_all)
        try:
            for name, spec in self.config.profiles.items():
                self._invoke_profile(engines[name], profile=spec)
        finally:
            self._exechooks(self.config.hooks.after_all)
        self.log.info("Finished!")

    def snapshots(self, repo: str, is_json=False):
        spec = self.config.repos.get(repo) if repo else self._default_repo
        if spec is None:
            raise KeyError(f"Unknown repo: {repo}")
        restic = Restic(spec, log=self.log)
        format = "json" if is_json else "text"
        return restic.snapshots(format=format)

    def _invoke_profile(self, restic, profile: config.Profile):
        with restic as engine:
            engine.backup(profile)
        self.log.info("Backup created successfully.")

    def _profile_for(self, name: str):
        result = self.config.profiles.get(name)
        if not result:
            raise KeyError(f"Unknown backup profile: {name!r}")
        return result
