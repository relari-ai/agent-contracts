from typing import Any, Dict

from agent_contracts.core.datatypes.verification.exec_path import ExecutionPath

IGNORE_KEYS = ["metadata"]


def exec_path_to_str_compact(
    exec_path: ExecutionPath,
    indent: int = 0,
    max_info_length: int = 50,
    include_state_info: bool = False,
) -> str:
    """Recursively formats the execution fragment with indentation and returns it as a string."""

    def process_info(info: Dict[str, Any], max_length: int = 30) -> str:
        """Formats info with two-level keys preserved, truncating deep values and adding type hints."""
        processed = {}
        for key, value in info.items():
            if key in IGNORE_KEYS:
                continue
            if isinstance(value, dict):  # Nested dict, keep two levels
                processed[key] = {}
                for sub_key, sub_value in value.items():
                    if isinstance(sub_value, (dict, set)):  # Dict or Set → Show type
                        processed[key][sub_key] = "{...}"
                    elif isinstance(sub_value, list):  # List → Show type
                        processed[key][sub_key] = "[...]"
                    else:
                        processed[key][sub_key] = (
                            str(sub_value)[:max_length] + "..."
                            if len(str(sub_value)) > max_length
                            else sub_value
                        )
            elif isinstance(value, list):  # Top-level list → Show type only
                processed[key] = "[...]"
            elif isinstance(
                value, (dict, set)
            ):  # Top-level dict or set → Show type only
                processed[key] = "{...}"
            else:  # String or other primitive type
                processed[key] = (
                    str(value)[:max_length] + "..."
                    if len(str(value)) > max_length
                    else value
                )
        return str(processed)  # Convert back to string for compact display

    output = []
    prefix = " " * indent
    output.append(f"{prefix}Trace ID: {exec_path.trace_id}")

    for state in exec_path.states:
        output.append(f"{prefix}  ├─ {state.name} (ID:{state.span_id})")

        # Process state info
        if include_state_info:
            info_text = process_info(state.info, max_info_length)
            output.append(f"{prefix}  │  ├─ info: {info_text}")

        # Process actions
        if state.actions:
            output.append(f"{prefix}  │  ├─ Actions:")
            for action in state.actions:
                action_info = process_info(action.info, max_info_length)
                output.append(f"{prefix}  │  │  ├─ {action.name} (ID:{action.span_id})")
                output.append(f"{prefix}  │  │  │  ├─ info: {action_info}")

    return "\n".join(output)  # Join the output list into a single string
