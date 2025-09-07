import subprocess as procs

from lohup import config
from lohup.logger import BasicLogger, LogLevel
from lohup.restic import Restic


class Lohup:
    def __init__(self, config_path: str | None, logger=None):
        self._config_path = config_path or "lohup.toml"
        self.config = None
        self.log = logger or BasicLogger(level=LogLevel.INFO)

    def load(self):
        self.config = config.TomlConfig.from_file(self._config_path, logger=self.log)

    def invoke_restic(self, repo: str, args: tuple[str, ...]):
        spec = self.config.repos.get(repo)
        if spec is None:
            raise KeyError(f"Unknown repo: {repo}")
        restic = Restic(spec, self.log)
        try:
            restic.run(args)
        except procs.CalledProcessError as e:
            self.log.error(e)

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

    def _repo_for(self, profile: config.Profile):
        default_list = list(filter(lambda x: x.default, self.config.repos.values()))
        default = default_list.pop() if default_list else None
        if profile.repo is not None:
            if repo := self.config.repos.get(profile.repo):
                return repo
            else:
                raise KeyError(f"No repo attached to profile: {profile.name!r}")
        if default is None:
            raise KeyError(f"No repo attached to profile: {profile.name!r}")
        return default

    def backup(self, profile: str):
        spec = self._profile_for(profile)
        repo = self._repo_for(spec)
        restic = Restic(repo, log=self.log)
        self._exechooks(self.config.hooks.before_all)
        try:
            self._invoke_profile(restic, profile=profile)
        finally:
            self._exechooks(self.config.hooks.after_all)
        self.log.info("Finished!")

    def backup_all(self):
        restics = {}
        for name, spec in self.config.profiles.items():
            restic = Restic(self._repo_for(spec), log=self.log)
            restics[name] = restic

        self._exechooks(self.config.hooks.before_all)
        try:
            for name, spec in self.config.profiles.items():
                restic = restics[name]
                self._invoke_profile(restic, profile=spec)
        finally:
            self._exechooks(self.config.hooks.after_all)
        self.log.info("Finished!")

    def snapshots(self, repo: str, is_json=False):
        spec = self.config.repos.get(repo)
        if spec is None:
            raise KeyError(f"Unknown repo: {repo}")
        restic = Restic(spec, log=self.log)
        format = "json" if is_json else "text"
        return restic.snapshots(format=format)

    def _invoke_profile(self, restic: Restic, profile: config.Profile):
        args = ["backup", "--tag", profile.name]
        match profile:
            case config.PathsProfile():
                args.append("--read-concurrency=6")
                for pth in profile.exclude_paths:
                    args.extend(["-e", pth])
                args.extend(profile.paths)
                restic.run(args)
            case config.CommandProfile():
                args.append("--stdin")
                restic.pipe_stdout(args, src_cmd=profile.command.split())
        self.log.info("Backup created successfully.")

    def _profile_for(self, name: str):
        result = self.config.profiles.get(name)
        if not result:
            raise KeyError(f"Unknown backup profile: {name!r}")
        return result
