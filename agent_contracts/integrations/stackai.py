import json
from pathlib import Path
from typing import List

from pydantic import BaseModel

from agent_contracts.core.datatypes.verification.exec_path import (
    Action,
    ExecutionPath,
    State,
)
from agent_contracts.core.utils.nanoid import nanoid

OUTPUT_SKIP_KEYS = {"delta"}
OTHER_SKIP_KEYS = {"state"}

class Graph(BaseModel):
    nodes: List[dict]
    edges: List[dict]

    def get_node(self, node_id: str) -> dict:
        for node in self.nodes:
            if node["id"] == node_id:
                return node
        raise ValueError(f"Node {node_id} not found")


class Run(BaseModel):
    run_id: str
    graph: Graph
    updates: List[dict]


def parse_run(graph_file: Path, data_file: Path) -> Run:
    with open(graph_file, "r") as f:
        graph_ = json.load(f)
    graph = Graph(nodes=graph_["nodes"], edges=graph_["edges"])
    updates = []
    with open(data_file, "r") as f:
        for line in f:
            line_ = line.strip()
            if not line_:
                continue
            elif line_.startswith("data:"):
                updates.append(json.loads(line[5:]))
            else:
                raise ValueError(f"Unknown line: {line_}")
    return Run(run_id=f"stackai-{nanoid(4)}", graph=graph, updates=updates)


def run_to_exec_path(run: Run) -> Path:
    input_ = dict()
    output_ = dict()
    states = []
    for idx, update in enumerate(run.updates):
        if (
            update["event_type"] == "node_result"
            and update["data"]["result"]["state"] == "SUCCESS"
        ):
            data = update["data"]
            node = run.graph.get_node(data["id"])
            if node["type"] == "in" and data["type"] == "in":
                input_[data["id"]] = data["result"]["inputs"]
            elif node["type"] == "out" and data["type"] == "out":
                output_[data["id"]] = {
                    k: v
                    for k, v in data["result"]["outputs"].items()
                    if k not in OUTPUT_SKIP_KEYS
                }
            else:
                info = {k:v for k,v in data["result"].items() if k not in OTHER_SKIP_KEYS} 
                states.append(
                    State(
                        span_id=f"update-{idx}",
                        name=data["name"],
                        actions=[Action(span_id=nanoid(8),name=data["type"],info=info)],
                    )
                )
    states.insert(
        0,
        State(
            span_id=nanoid(8),
            name="Start",
            actions=[Action(span_id=nanoid(8),name="Input",info=input_)],
        ),
    )
    states.append(
        State(
            span_id=nanoid(8),
            name="End",
            actions=[Action(span_id=nanoid(8),name="Output",info=output_)],
        )
    )
    return ExecutionPath(trace_id=run.run_id, states=states)
