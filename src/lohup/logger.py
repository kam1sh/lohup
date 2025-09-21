from dataclasses import dataclass, field
import click
import logging
import enum


class LogLevel(enum.IntEnum):
    ERROR = 40
    WARNING = 30
    INFO = 20
    VERBOSE = 15
    DEBUG = 10
    TRACE = 5


@dataclass
class CliLogger:
    level: LogLevel = field(default=LogLevel.INFO)

    def error(self, msg):
        if self.level <= LogLevel.ERROR:
            if isinstance(msg, Exception):
                import traceback

                msg = "".join(traceback.format_exception(msg))
            msg = (click.style("[error]", fg="red"), msg)
            click.echo(" ".join(msg))

    def warning(self, msg):
        if self.level <= LogLevel.WARNING:
            msg = (click.style("[warn]", fg="orange"), msg)
            click.echo(" ".join(msg))

    def info(self, msg):
        if self.level <= LogLevel.INFO:
            msg = (click.style("[info]", fg="blue"), msg)
            click.echo(" ".join(msg))

    def debug(self, msg):
        if self.level <= LogLevel.DEBUG:
            msg = (click.style("[debug]", fg="white"), msg)
            click.echo(" ".join(msg))

    def accepts(self, level):
        return self.level <= level


class BasicLogger:
    LEVEL_DEBUG = logging.DEBUG
    LEVEL_INFO = logging.INFO
    LEVEL_ERROR = logging.ERROR

    def __init__(self, level=LogLevel.DEBUG):
        self.level = level
        self.logger = logging.Logger("lohup", level=level.value)

    def error(self, msg):
        if isinstance(msg, Exception):
            self.logger.error("Got exception", exc_info=msg)
        else:
            self.logger.error(msg)

    def warning(self, msg):
        self.logger.warning(msg)

    def info(self, msg):
        self.logger.info(msg)

    def debug(self, msg):
        self.logger.debug(msg)

    def accepts(self, level):
        return self.level <= level


LoggerProto = CliLogger | BasicLogger
