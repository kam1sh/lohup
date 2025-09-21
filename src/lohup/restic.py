from pathlib import Path
from dataclasses import dataclass, field
import os
import subprocess as procs
import json

from lohup import config
from lohup.logger import CliLogger, BasicLogger


@dataclass
class Restic:
    repo: config.Repository
    log: CliLogger | BasicLogger
    binary: str = field(default="restic")

    def environ(self):
        env = os.environ.copy()
        env["RESTIC_PASSWORD_FILE"] = self.repo.repo_key_file.value
        match self.repo:
            case config.S3Repository():
                if value := self.repo.region:
                    env["AWS_DEFAULT_REGION"] = value
                if masked := self.repo.access_key_file:
                    env["AWS_ACCESS_KEY_ID"] = Path(masked.value).read_text().strip()
                if masked := self.repo.secret_key_file:
                    env["AWS_SECRET_ACCESS_KEY"] = (
                        Path(masked.value).read_text().strip()
                    )
                path = self.repo.path.lstrip("/")
                url = f"{self.repo.endpoint}/{self.repo.bucket}/{path}"
                env["RESTIC_REPOSITORY"] = f"s3:{url}"
            case config.LocalRepository():
                env["RESTIC_REPOSITORY"] = self.repo.path
        return env

    def run(self, args):
        cmd, env = self._prepare(args)
        procs.check_call(cmd, env=env)

    def backup(self, profile: config.Profile):
        args = ["backup", "--tag", profile.name]
        args.extend(profile.cli_args)
        match profile:
            case config.PathsProfile():
                for pth in profile.exclude_paths:
                    args.extend(["-e", pth])
                args.extend(profile.paths)
                self.run(args)
            case config.CommandProfile():
                args.append("--stdin")
                match profile.command:
                    case str(x):
                        self.pipe_stdout(args, src_cmd=x.split())
                    case list(x):
                        self.pipe_stdout(args, src_cmd=x)
                    case _:
                        raise NotImplementedError(profile.command)

    def pipe_stdout(self, args: list[str], src_cmd: list[str]):
        cmd = [self.binary] + args
        env = self.environ()
        with procs.Popen(cmd, stdin=procs.PIPE, env=env) as restic:
            procs.check_call(src_cmd, stdout=restic.stdin)

    def snapshots(self, format="text"):
        cmd, env = self._prepare(["snapshots", "--compact"])
        if format == "json":
            cmd.append("--json")
        result = procs.check_output(cmd, env=env, encoding="utf-8")
        if format == "json":
            return json.loads(result)
        return result

    def _prepare(self, args: list[str]):
        if self.repo is None:
            raise ValueError("repo not set")
        cmd = [self.binary]
        cmd.extend(args)
        env = self.environ()
        return cmd, env

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        return self
