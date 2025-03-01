from os import getenv
from pathlib import Path

import yaml
from loguru import logger
from pydantic import BaseModel

from agent_contracts.core.verification.configs import (
    NLVerificationConfig,
    PathconditionConfig,
    PostconditionConfig,
    PreconditionConfig,
)


class Pathconditions(BaseModel):
    multi_stage: NLVerificationConfig = NLVerificationConfig()
    simple: PathconditionConfig = PathconditionConfig()


class Preconditions(BaseModel):
    simple: PreconditionConfig = PreconditionConfig()


class Postconditions(BaseModel):
    simple: PostconditionConfig = PostconditionConfig()


class Settings(BaseModel):
    verbose: bool = False
    pathconditions: Pathconditions = Pathconditions()
    preconditions: Preconditions = Preconditions()
    postconditions: Postconditions = Postconditions()

    @classmethod
    def from_yaml(cls, file_path: str) -> "Settings":
        logger.info(f"Loading config from {file_path}")
        with Path(file_path).open() as f:
            config_data = yaml.safe_load(f)
        return cls(**config_data)


__VERIFICATION_CONFIG_FILE = getenv("VERIFICATION_CONFIG", None)
VerificationConfig = (
    Settings.from_yaml(__VERIFICATION_CONFIG_FILE)
    if __VERIFICATION_CONFIG_FILE
    else Settings()
)
