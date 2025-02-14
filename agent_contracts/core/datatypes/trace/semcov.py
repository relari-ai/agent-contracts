RELARI_TRACER = "relari-otel"


class EvalAttributes:
    DATASET_ID = "eval.dataset.id"
    RUN_ID = "eval.run.id"
    SCENARIO_ID = "eval.uuid"
    PROJECT_NAME = "openinference.project.name"

class OpeninferenceInstrumentators:
    CREWAI = "openinference.instrumentation.crewai"
    LANGCHAIN = "openinference.instrumentation.langchain"
