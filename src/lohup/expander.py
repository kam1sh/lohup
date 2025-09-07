from dataclasses import dataclass
import re


@dataclass
class VarExpander:
    globalvars: dict[str, str]
    _PATTERN = re.compile(r"(\$([\w_]+)[^\w_/$]*)+")

    def expand(self, text: str | None, extras: dict[str, str] | None = None):
        if not text or "$" not in text:
            return text
        all_vars = self.globalvars.copy()
        if extras:
            all_vars.update(extras)
        match = self._PATTERN.findall(text)
        if not match:
            return
        for var, name in match:
            value = all_vars.get(name)
            if not value:
                raise KeyError(f"variable {var} is not defined")
            text = text.replace(var, value)
        return text

    @staticmethod
    def from_conf(settings):
        return VarExpander(globalvars=settings.globalvars)
