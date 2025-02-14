from typing import Any, Dict, List

from anytree import PreOrderIter

from agent_contracts.core.datatypes.trace import Trace

IGNORED_NODES = [
    "__start__",
    "__end__",
    "_write",
    "RunnableSequence",
    "ChatPromptTemplate",
    "PydanticToolsParser",
    "StateModifier",
    "call_model",
    "Unnamed",
    "should_continue",
    "Prompt",
]

AGENT_NODE = "agent"


def should_include(node) -> bool:
    return node.name not in IGNORED_NODES


def _item(span, actions=None):
    obj = {
        "spanId": span.span_id,
        "name": span.name,
        "info": span.attributes,
    }
    if actions:
        obj["actions"] = actions
    return obj


def is_descendant(span, state_ids):
    return any(x.span_id in state_ids for x in span.path)


def exec_path_from_trace(trace: Trace) -> List[Dict[str, Any]]:
    if not trace.root:
        raise ValueError("No root span found!")
    states = []
    state_ids = set()
    for span in PreOrderIter(trace.root):
        # consider only agent spans
        if span.kind.lower() == AGENT_NODE:
            # Check if this is a descendant of a state already in the exec path
            if is_descendant(span, state_ids):
                # TODO: this might not be always the correct behavior
                continue
            # collect actions from the leaves of the span
            actions = [_item(leaf) for leaf in span.leaves if should_include(leaf)]
            if actions:
                # add the state to the exec path
                states.append(_item(span, actions))
                state_ids.add(span.span_id)
    return states
