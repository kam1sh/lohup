from lohup.app import Lohup
from lohup.config import ConfigError
from lohup.logger import BasicLogger, LogLevel

import pytest

toml1 = """
[settings.globals]
"""

toml2 = """
[[hooks.before-all]]
kind = "unknown"
foo = "bar"

[repos.local]
kind = "local"
path = "{base}/repo"
repo-key-file = "{pwfile}"
"""


class RepoEnvironment:
    def __init__(self, tmp_path):
        self.basepath = tmp_path
        self.log = BasicLogger(level=LogLevel.DEBUG)

    def write_password(self, value: str = "1"):
        pth = self.basepath / "password.txt"
        pth.write_text("1")
        return pth


def test_error_message(tmp_path):
    env = RepoEnvironment(tmp_path)
    pwfile = env.write_password()
    path = tmp_path / "lohup.toml"
    path.write_text(toml1.format(base=tmp_path, pwfile=pwfile))
    app = Lohup(config_path=path, logger=env.log)
    msg = "no repositories defined"
    with pytest.raises(ConfigError, match="Failed to parse TOML config") as exc:
        app.load()
    env.log.error(exc.value)
    assert str(exc.value.__cause__) == msg


def test_hook_error(tmp_path):
    env = RepoEnvironment(tmp_path)
    pwfile = env.write_password()
    tmp_path.joinpath("repo").mkdir()
    path = tmp_path / "lohup.toml"
    path.write_text(toml2.format(base=tmp_path, pwfile=pwfile))
    app = Lohup(config_path=path, logger=env.log)
    msg = "hook: Unsupported before-all: unknown"
    with pytest.raises(ConfigError, match="Failed to parse TOML config") as exc:
        app.load()
    env.log.error(exc.value)
    assert str(exc.value.__cause__) == msg
