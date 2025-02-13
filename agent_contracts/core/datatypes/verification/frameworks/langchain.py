from typing import Any, Dict, List

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


def should_include_node(node) -> bool:
    return node.name not in IGNORED_NODES


def get_all_leaves(span):
    """Recursively collect all leaf nodes in a span's subtree."""
    leaves = []
    for descendant in span.descendants:
        if not should_include_node(descendant):
            continue
        if not descendant.children:  # is leaf
            leaves.append(  # action
                {
                    "spanId": descendant.span_id,
                    "name": descendant.name,
                    "info": descendant.attributes,
                }
            )
    return leaves


def exec_path_from_trace(trace: Trace) -> List[Dict[str, Any]]:
    root = trace.root
    if not root:
        raise ValueError("No root span found!")
    states = []
    # Count LangGraph nodes first
    langgraph_nodes = [node for node in root.children if node.name == "LangGraph"]
    add_turn_numbers = len(langgraph_nodes) > 1
    # Process each LangGraph node
    for turn_num, node in enumerate(langgraph_nodes, 1):
        # Get states from children of LangGraph nodes
        for state_span in node.children:
            if not should_include_node(state_span):
                continue
            state_name = state_span.name
            if add_turn_numbers:
                state_name = f"{state_name} (turn {turn_num})"
            state = {
                "spanId": state_span.span_id,
                "name": state_name,
                "info": state_span.attributes,
                "actions": get_all_leaves(state_span),
            }
            if state["actions"]:  # Only include states that have actions
                states.append(state)
    return states
