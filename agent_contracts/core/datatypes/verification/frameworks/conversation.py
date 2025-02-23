import ast
import re
import hashlib
from collections import defaultdict, deque


def parse_kv_string(s):
    """
    Deserialize a string of key=value pairs (with possible nested structures)
    into the corresponding Python dictionary.

    Examples:
      Input:  "content='Hello' additional_kwargs={'refusal': None} id='abc'"
      Output: {
          "content": "Hello",
          "additional_kwargs": {"refusal": None},
          "id": "abc"
      }
    """
    result = {}
    i = 0
    n = len(s)

    while i < n:
        # Skip any leading whitespace
        while i < n and s[i].isspace():
            i += 1
        if i >= n:
            break

        # Read key: characters until '='
        key_start = i
        while i < n and s[i] != "=":
            i += 1
        key = s[key_start:i].strip()
        i += 1  # skip '='

        # Now parse the value.
        # We'll grab characters until we hit a top-level whitespace (i.e. not inside
        # a string or nested structure like {} or [] or ())
        val_start = i
        stack = []
        in_quote = None
        escape = False

        while i < n:
            ch = s[i]
            if in_quote:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == in_quote:
                    in_quote = None
                i += 1
                continue
            else:
                if ch in ('"', "'"):
                    in_quote = ch
                    i += 1
                    continue
                elif ch in "{[(":
                    stack.append(ch)
                elif ch in "}])":
                    if stack:
                        stack.pop()
                elif ch.isspace():
                    # if we're not inside any nested structure, break out
                    if not stack:
                        break
                i += 1

        val_str = s[val_start:i].strip()

        # Some values (e.g. Decimal('20')) are not literal-evaluable.
        # Replace Decimal('...') with just the inner number.
        val_str = re.sub(r"Decimal\((['\"])(.*?)\1\)", lambda m: m.group(2), val_str)

        # Use ast.literal_eval to convert the literal string to a Python object.
        try:
            value = ast.literal_eval(val_str)
        except Exception:
            # if evaluation fails, keep the raw string
            value = val_str

        # Special handling:
        # In example 4, the "content" field is itself a dictionary serialized as a string.
        # So if key is "content" and value is a string that looks like a dict, try to parse it.
        if (
            key == "content"
            and isinstance(value, str)
            and value.strip().startswith("{")
            and value.strip().endswith("}")
        ):
            try:
                value = ast.literal_eval(value)
            except Exception:
                pass

        result[key] = value

        # Skip trailing whitespace before the next pair
        while i < n and s[i].isspace():
            i += 1

    return result


def reconstruct_order(ids):
    # Create a graph and a dictionary to count the indegree of each message.
    graph = defaultdict(set)
    indegree = {}

    # Initialize all message IDs in indegree to ensure they all appear
    for sub in ids:
        for msg in sub:
            if msg not in indegree:
                indegree[msg] = 0

    # Build the graph based on the ordering constraints in each sublist.
    for sub in ids:
        for i in range(len(sub) - 1):
            # For each consecutive pair, add an edge if it hasn't been added already.
            a, b = sub[i], sub[i + 1]
            if b not in graph[a]:
                graph[a].add(b)
                indegree[b] += 1

    # Perform a topological sort.
    queue = deque([msg for msg in indegree if indegree[msg] == 0])
    order = []
    while queue:
        current = queue.popleft()
        order.append(current)
        for neighbor in graph[current]:
            indegree[neighbor] -= 1
            if indegree[neighbor] == 0:
                queue.append(neighbor)

    # Check if the ordering is valid (i.e., all messages are included)
    if len(order) != len(indegree):
        raise ValueError("Cycle detected or incomplete ordering!")
    return order


def parse_conversation(exec_path):
    state_messages = {}
    ids = []
    for state in exec_path.states:
        try:
            msgs_str = state.info["input"]["messages"]
        except KeyError:
            msgs_str = []
        msgs_in = [parse_kv_string(msg) for msg in msgs_str]
        try:
            msgs_str = state.info["output"]["messages"]
        except KeyError:
            msgs_out = []
        msgs_out = [parse_kv_string(msg) for msg in msgs_str]
        already_seen = set()
        local_ids = []
        for m in msgs_in:
            try:
                msg_id = hashlib.sha256(m["content"].encode()).hexdigest()
            except (AttributeError, UnicodeEncodeError, TypeError):
                continue
            if msg_id not in already_seen:
                already_seen.add(msg_id)
                local_ids.append(msg_id)
                state_messages[msg_id] = {"__type__": "input", **m}
        for m in msgs_out:
            try:
                msg_id = hashlib.sha256(m["content"].encode()).hexdigest()
            except (AttributeError, UnicodeEncodeError, TypeError):
                continue
            if msg_id not in already_seen:
                already_seen.add(msg_id)
                local_ids.append(msg_id)
                state_messages[msg_id] = {"__type__": "output", **m}
        ids.append(local_ids)
    order = reconstruct_order(ids)
    messages_ = [
        state_messages[id]
        for id in order
        if ("content" in state_messages[id] and state_messages[id]["content"])
        and "tool_call_id" not in state_messages[id]
    ]
    messages = []
    for m in messages_:
        if ("response_metadata" in m and m["response_metadata"]) or m[
            "__type__"
        ] == "output":
            messages.append({"role": "assistant", "content": m["content"]})
        else:
            messages.append({"role": "user", "content": m["content"]})
    return messages
