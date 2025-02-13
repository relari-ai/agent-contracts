from agent_contracts.core.datatypes.trace import Framework, Trace

from .langchain import exec_path_from_trace as exec_path_from_langchain_trace


def parse_trace(trace: Trace):  # type: ignore
    if trace.info.framework == Framework.LANGCHAIN:
        return exec_path_from_langchain_trace(trace)
    else:
        raise ValueError(f"Unsupported framework: {trace.framework}")
