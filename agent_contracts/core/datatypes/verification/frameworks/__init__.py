from agent_contracts.core.datatypes.trace import Framework, Trace

from .langchain import exec_path_from_trace as exec_path_from_langchain_trace


def parse_trace(trace: Trace):  # type: ignore
    default_parser = exec_path_from_langchain_trace
    if trace.info.framework == Framework.LANGCHAIN:
        return exec_path_from_langchain_trace(trace)
    else:
        return default_parser(trace)
