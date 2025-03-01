from pydantic import BaseModel


class SimpleConfig(BaseModel):
    model: str = "gpt-4o-mini"

    def model_params(self, **kwargs) -> dict:
        return {"model": self.model, **kwargs}


# ==============================================
# Preconditions
# ==============================================

## Simple


class PreconditionConfig(SimpleConfig):
    prompt: str = "verification/precondition"


# ==============================================
# Pathconditions
# ==============================================

## Multi-Stage


class StepConfig(BaseModel):
    init: str
    step: str
    verify: str


class NLVerificationConfig(BaseModel):
    models: StepConfig = StepConfig(
        init="o3-mini", step="gpt-4o-mini", verify="o3-mini"
    )
    prompts: StepConfig = StepConfig(
        init="verification/pathcondition/init",
        step="verification/pathcondition/step",
        verify="verification/pathcondition/verify",
    )
    early_termination: bool = True


## Simple


class PathconditionConfig(SimpleConfig):
    model: str = "o3-mini"
    prompt: str = "verification/pathcondition/single/"


# ==============================================
# Pathconditions
# ==============================================

## Simple


class PostconditionConfig(SimpleConfig):
    prompt: dict = {
        "output": "verification/postcondition/output",
        "conversation": "verification/postcondition/conversation",
    }
