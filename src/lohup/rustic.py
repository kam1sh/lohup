from pathlib import Path
from dataclasses import dataclass, field
import subprocess as procs
import json
import tomlkit

from lohup import config
from lohup.logger import LoggerProto


@dataclass
class Rustic:
    repo: config.Repository
    log: LoggerProto
    conf_dir: Path
    binary: str = field(default="rustic")

    @property
    def conf_file(self) -> Path:
        return self.conf_dir / "rustic.toml"

    def write_config(self) -> Path:
        out = {}
        repo_pass = Path(self.repo.repo_key_file.value).read_text().strip()
        out["repository"] = {"password": repo_pass}
        match self.repo:
            case config.S3Repository():
                out["repository"]["repository"] = "opendal:s3"
                opts = {}
                if masked := self.repo.access_key_file:
                    opts["access_key_id"] = Path(masked.value).read_text().strip()
                if masked := self.repo.secret_key_file:
                    opts["secret_access_key"] = Path(masked.value).read_text().strip()
                opts["endpoint"] = self.repo.endpoint
                opts["bucket"] = self.repo.bucket
                opts["root"] = self.repo.path
                opts["region"] = self.repo.region
                out["repository"]["options"] = opts
            case config.LocalRepository():
                out["repository"]["repository"] = self.repo.path
        self.conf_dir.mkdir(exist_ok=True)
        with self.conf_file.open("w") as f:
            tomlkit.dump(out, f)

    def _cmdline(self):
        out = [self.binary, "--log-level=warn", "-P", str(self.conf_dir / "rustic")]
        return out

    def run(self, args):
        cmd = self._cmdline()
        cmd.extend(args)
        procs.check_call(cmd)

    def backup(self, profile: config.Profile):
        args = ["backup", "--tag", profile.name]
        args.extend(profile.cli_args)
        match profile:
            case config.PathsProfile():
                for pth in profile.exclude_paths:
                    args.extend(["--glob", f"!{pth}"])
                args.extend(profile.paths)
                self.run(args)
            case config.CommandProfile():
                args.append("-")
                match profile.command:
                    case str(x):
                        self.pipe_stdout(args, src_cmd=x.split())
                    case list(x):
                        self.pipe_stdout(args, src_cmd=x)

    def pipe_stdout(self, args: list[str], src_cmd: list[str]):
        cmd = self._cmdline()
        cmd.extend(args)
        with procs.Popen(cmd, stdin=procs.PIPE) as rustic:
            procs.check_call(src_cmd, stdout=rustic.stdin)

    def snapshots(self, format="text"):
        cmd = self._cmdline()
        cmd.extend(["snapshots", "--compact"])
        if format == "json":
            cmd.append("--json")
        result = procs.check_output(cmd, encoding="utf-8")
        if format == "json":
            return json.loads(result)
        return result

    def __enter__(self):
        self.write_config()
        return self

    def __exit__(self, type, value, traceback):
        self.conf_file.unlink(True)
