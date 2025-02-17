RELARI_TRACER = "relari-otel"


class EvalAttributes:
    RUN_ID = "eval.run.id"
    DATASET_ID = "eval.dataset.id"
    SCENARIO_ID = "eval.scenario.id"
    PROJECT_NAME = "openinference.project.name"

class OpeninferenceInstrumentators:
    CREWAI = "openinference.instrumentation.crewai"
    LANGCHAIN = "openinference.instrumentation.langchain"
