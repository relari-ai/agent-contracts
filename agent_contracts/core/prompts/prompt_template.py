from pathlib import Path
from typing import Optional, Set

from jinja2 import BaseLoader, Environment, meta


class PromptTemplate:
    def __init__(
        self,
        user_prompt: str,
        system_prompt: Optional[str] = None,
    ):
        self._env = Environment(loader=BaseLoader())
        self._raw_system_prompt = system_prompt
        self._raw_user_prompt = user_prompt
        if self._raw_system_prompt is not None:
            self._sys_prompt_template = self._env.from_string(self._raw_system_prompt)
        else:
            self._sys_prompt_template = None
        self._user_prompt_template = self._env.from_string(self._raw_user_prompt)
        self._vars = self._get_vars(self._raw_user_prompt) | self._get_vars(
            self._raw_system_prompt
        )

    def _get_vars(self, prompt: Optional[str]) -> Set[str]:
        if prompt is None:
            return set()
        ast = self._env.parse(prompt)
        return meta.find_undeclared_variables(ast)

    def system(self, **kwargs) -> Optional[str]:
        if self._sys_prompt_template is None:
            return None
        return self._sys_prompt_template.render(**kwargs)

    def user(self, **kwargs) -> str:
        return self._user_prompt_template.render(**kwargs)

    def render(self, **kwargs):
        msgs = []
        sys = self.system(**kwargs)
        usr = self.user(**kwargs)
        if sys is not None:
            msgs.append({"role": "system", "content": sys})
        msgs.append({"role": "user", "content": usr})
        return msgs
    
    @classmethod
    def from_file(
        cls,
        user_prompt_path: Path,
        system_prompt_path: Optional[Path] = None,
    ):
        if system_prompt_path is None:
            system_prompt = None
        else:
            with open(system_prompt_path, "r") as f:
                system_prompt = f.read()
        with open(user_prompt_path, "r") as f:
            user_prompt = f.read()
        return cls(system_prompt=system_prompt, user_prompt=user_prompt)
