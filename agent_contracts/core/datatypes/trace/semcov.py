RELARI_TRACER = "relari-otel"


class EvalAttributes:
    SPECIFICATIONS_ID = "relari.eval.dataset.id"
    SCENARIO_ID = "relari.eval.scenario.id"
    OUTPUT = "relari.eval.output"


class ResourceAttributes:
    RUN_ID = "relari.eval.run.id"
    PROJECT_NAME = "openinference.project.name"
    CERTIFICATION_ENABLED = "relari.certification.enabled"


class OpeninferenceInstrumentators:
    CREWAI = "openinference.instrumentation.crewai"
    LANGCHAIN = "openinference.instrumentation.langchain"
