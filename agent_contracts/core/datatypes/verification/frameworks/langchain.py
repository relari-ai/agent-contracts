from typing import Any, Dict, List

from anytree import LevelOrderIter

from agent_contracts.core.datatypes.trace import Trace

IGNORED_NODES = [
    "__start__",
    "__end__",
    "_write",
    "ChatPromptTemplate",
    "StateModifier",
    "call_model",
    "Unnamed",
    "should_continue",
    "Prompt",
    "LangGraph",
    "RunnableLambda",
]

ROOT_NODES = ["root", "eval-start"]


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
    # First find all top-level nodes (states)
    state_nodes, state_ids = [], set()
    for span in LevelOrderIter(trace.root, filter_=should_include):
        if span.name in ROOT_NODES or is_descendant(span, state_ids):
            continue
        state_nodes.append(span)
        state_ids.add(span.span_id)
    # Then find all actions for each state
    states = []
    for span in state_nodes:
        actions = [_item(leaf) for leaf in span.leaves if should_include(leaf)]
        if actions:
            states.append(_item(span, actions))
    return states
