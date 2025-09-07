from dataclasses import dataclass, field
import click
import logging
import enum


class LogLevel(enum.IntEnum):
    ERROR = 40
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
            click.echo(click.style(msg, fg="red"))

    def info(self, msg):
        if self.level <= LogLevel.INFO:
            click.echo(click.style(msg, fg="blue"))

    def debug(self, msg):
        if self.level <= LogLevel.DEBUG:
            click.echo(click.style(msg, fg="white"))

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

    def info(self, msg):
        self.logger.info(msg)

    def debug(self, msg):
        self.logger.debug(msg)

    def accepts(self, level):
        return self.level <= level
