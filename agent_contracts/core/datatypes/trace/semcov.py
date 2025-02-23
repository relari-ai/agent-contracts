RELARI_TRACER = "relari-otel"


class EvalAttributes:
    RUN_ID = "relari.eval.run.id"
    SPECIFICATIONS_ID = "relari.eval.dataset.id"
    SCENARIO_ID = "relari.eval.scenario.id"
    PROJECT_NAME = "openinference.project.name"
    OUTPUT = "relari.eval.output"

class OpeninferenceInstrumentators:
    CREWAI = "openinference.instrumentation.crewai"
    LANGCHAIN = "openinference.instrumentation.langchain"
