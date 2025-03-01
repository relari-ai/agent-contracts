from pathlib import Path
from typing import Optional

from jinja2 import BaseLoader, Environment, FileSystemLoader, meta


class PromptTemplate:
    def __init__(self, user_prompt, system_prompt=None):
        # If the given prompt is a precompiled Jinja2 template (has render), use it.
        if hasattr(user_prompt, "render"):
            self._user_prompt_template = user_prompt
            self._env = user_prompt.environment
            self._raw_user_prompt = None
        else:
            self._env = Environment(loader=BaseLoader())
            self._raw_user_prompt = user_prompt
            self._user_prompt_template = self._env.from_string(user_prompt)

        if system_prompt is not None:
            if hasattr(system_prompt, "render"):
                self._sys_prompt_template = system_prompt
                self._raw_system_prompt = None
            else:
                self._raw_system_prompt = system_prompt
                self._sys_prompt_template = self._env.from_string(system_prompt)
        else:
            self._sys_prompt_template = None
            self._raw_system_prompt = None

        # Compute the set of undeclared variables (if using raw strings)
        self._vars = set()
        if self._raw_user_prompt is not None:
            self._vars |= self._get_vars(self._raw_user_prompt)
        if self._raw_system_prompt is not None:
            self._vars |= self._get_vars(self._raw_system_prompt)

    def _get_vars(self, prompt):
        ast = self._env.parse(prompt)
        return meta.find_undeclared_variables(ast)

    def system(self, **kwargs) -> str:
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
        # Create a set of directories to search for templates.
        search_dirs = {str(user_prompt_path.parent)}
        if system_prompt_path is not None:
            search_dirs.add(str(system_prompt_path.parent))

        # Create an environment using a FileSystemLoader so that include statements work.
        env = Environment(loader=FileSystemLoader(list(search_dirs)))

        # Load the user template using its file name.
        user_template = env.get_template(user_prompt_path.name)

        # Likewise load the system template if provided.
        system_template = (
            env.get_template(system_prompt_path.name) if system_prompt_path else None
        )

        # Note: The __init__ of PromptTemplate must be updated to accept
        # jinja2.Template objects (for example, checking for a callable render() method).
        return cls(user_prompt=user_template, system_prompt=system_template)
