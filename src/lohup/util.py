from pathlib import Path
from dataclasses import dataclass, field
from contextlib import contextmanager


@dataclass(repr=False)
class Masked:
    value: str

    def __str__(self):
        return "[masked]"


@contextmanager
def catch_errors(sep="\n", prefix=None, failfast=False):
    catcher = ErrorCatcher(prefix=prefix, failfast=failfast)
    try:
        yield catcher
    except:
        raise
    catcher.verify(sep=sep)


@dataclass
class ErrorCatcher:
    outer_prefix: str | None = field(default=None)
    prefix: str | None = field(default=None)
    errorlist: list = field(default_factory=list)
    failfast: bool = field(default=False)

    def catch(self, func, prefix=None):
        try:
            return func()
        except CatcherError as e:
            if e.catcher.prefix:
                e.catcher.outer_prefix = prefix
            else:
                e.catcher.prefix = prefix
            self.errorlist.append(e)
        except Exception as e:
            if self.failfast:
                raise
            self.errorlist.append(e)

    def error(self, msg):
        self.errorlist.append(msg)

    def verify(self, sep="\n"):
        result = self.lines()
        if result:
            raise CatcherError(
                sep.join(self._prefixed(x) for x in result), catcher=self
            )

    def lines(self):
        out = []
        extras = []
        for err in self.errorlist:
            match err:
                case str():
                    out.append(err)
                case CatcherError():
                    extras.extend(err.catcher.lines())
                case _:
                    extras.append(str(err))
        out.extend(extras)
        return [self._prefixed(x) for x in out]

    def _prefixed(self, s):
        if self.outer_prefix:
            return f"{self.outer_prefix} {self.prefix} {s}"
        return f"{self.prefix} {s}" if self.prefix else s


class CatcherError(ValueError):
    catcher: ErrorCatcher

    def __init__(self, message, catcher=None):
        self.catcher = catcher
        super().__init__(message)


def ensure_exists(name, expect="file", field=None) -> str | None:
    if not name:
        if field is not None:
            return f"field {field!r}: empty value"
        return "empty value"
    pth = Path(str(name))
    if isinstance(name, Masked):
        pth = Path(name.value)
    msg = None
    if not pth.exists():
        msg = f"file {name} not found"
    elif expect == "file" and not pth.is_file():
        msg = f"{name}: not a file"
    elif expect == "dir" and not pth.is_dir():
        msg = f"{name}: not a directory"
    if msg is not None and field is not None:
        return f"field {field!r}: {msg}"
    return msg
