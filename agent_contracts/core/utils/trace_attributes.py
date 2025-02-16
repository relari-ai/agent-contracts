import json_repair
from typing import Dict, Any


def attribute_value(attribute: Dict[str, Any]):
    if "value" not in attribute:
        return attribute
    value = attribute["value"]
    if isinstance(value, dict):
        if "stringValue" in attribute["value"]:
            rep = json_repair.loads(attribute["value"]["stringValue"])
            return rep or attribute["value"]["stringValue"]
        elif "intValue" in attribute["value"]:
            return int(attribute["value"]["intValue"])
        elif "boolValue" in attribute["value"]:
            return bool(attribute["value"]["boolValue"])
        elif "doubleValue" in attribute["value"]:
            return float(attribute["value"]["doubleValue"])
        else:
            return attribute["value"]
    else:
        if "type" in attribute:
            type_val = attribute["type"]
            if type_val == "string":
                return str(value)
            elif type_val == "int":
                return int(value)
            elif type_val == "bool":
                return bool(value)
    return value


def get_attribute_value(trace: dict, key: str, default: Any = None) -> str | None:
    tag = find_attribute(trace, key)
    return attribute_value(tag) if tag else default


def find_attribute(trace: dict, key: str) -> str | None:
    if not trace:
        return None
    try:
        _tags = trace["attributes"]
    except (KeyError, TypeError):
        try:
            _tags = trace.attributes
        except AttributeError:
            if isinstance(trace, list):
                _tags = trace
            else:
                raise ValueError("Invalid trace type")
    if _tags is None:
        return None
    for tag in _tags:
        if tag["key"] == key:
            return tag
    return None


def recreate_attributes_hierarchy(items):
    root = {}
    for entry in items:
        path_str = entry["key"]
        value = entry["value"]
        try:
            parsed_value = json_repair.loads(value)
        except Exception:
            parsed_value = None
        path = [int(p) if p.isdigit() else p for p in path_str.split(".")]
        insert_into(root, path, parsed_value or value)
    return root


def insert_into(current, path, value):
    if not path:
        return value
    key = path[0]
    rest = path[1:]
    if isinstance(key, int):
        if not isinstance(current, list):
            current = []
        while len(current) <= key:
            current.append(None)
        if not rest:
            current[key] = value
        else:
            current[key] = insert_into(current[key], rest, value)
        return current
    else:
        if not isinstance(current, dict):
            current = {}
        if not rest:
            current[key] = value
        else:
            current[key] = insert_into(current.get(key), rest, value)
        return current
