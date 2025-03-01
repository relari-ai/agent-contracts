from random import choices
from string import hexdigits
from typing import Any, Dict, List, Optional

from anytree import PreOrderIter, RenderTree
from anytree.exporter import DictExporter
from pydantic import BaseModel

from agent_contracts.core.datatypes.trace.semcov import (
    EvalAttributes,
    OpeninferenceInstrumentators,
    ResourceAttributes,
)
from agent_contracts.core.utils.trace_attributes import get_attribute_value

from .common import Framework, Span


class TraceExporter(DictExporter):
    @staticmethod
    def _iter_attr_values(node):
        # pylint: disable=C0103
        for k, v in node.__dict__.items():
            if k in ("_NodeMixin__children", "_NodeMixin__parent", "raw_attributes"):
                continue
            yield k, v


class TraceInfo(BaseModel):
    framework: Framework = Framework.UNKNOWN
    project_name: Optional[str] = None
    run_id: Optional[str] = None
    specifications_id: Optional[str] = None
    scenario_id: Optional[str] = None
    start_time: Optional[int] = None
    duration: Optional[int] = None

    @property
    def is_complete(self):
        return (
            self.project_name is not None
            and self.run_id is not None
            and self.scenario_id is not None
            and self.specifications_id is not None
            and self.framework is not None
        )


class Trace:
    def __init__(self, trace_id: str, trace: dict, **kwargs):
        self._raw_trace = trace
        self.trace_id: str = trace_id
        self.trace: List[Span] = self._build(trace)
        self.info: TraceInfo = self._analyze()
        self.metadata = kwargs
        self.root = self._find_root()

    def _find_root(self):
        # Find all root spans
        roots = [node for node in self.trace if node.is_root]
        if len(roots) > 1:
            start = min(root.start_time for root in roots)
            end = max(root.end_time for root in roots)
            new_root = Span(
                span_id=self._generate_span_id(),
                name="root",
                kind="ROOT",
                attributes={},
                start_time=start,
                end_time=end,
                children=roots,
            )
            for root in roots:
                root.parent = new_root
            return new_root
        return roots[0]

    @staticmethod
    def _generate_span_id():
        return "".join(choices(hexdigits.lower(), k=16))

    def _build(self, trace_data):
        # Sort by startTime and extract spans
        spans = sorted(trace_data, key=lambda x: x["startTime"])
        nodes = {
            span["spanID"]: Span(
                span_id=span["spanID"],
                name=span["name"],
                kind=span["kind"],
                attributes=span["attributes"],
                start_time=span["startTime"],
                end_time=span["endTime"],
            )
            for span in spans
        }
        # Set up parent-child relationships
        for span in spans:
            span_id = span["spanID"]
            parent_span_id = span.get("parentSpanID", None)
            if parent_span_id and parent_span_id in nodes:
                nodes[span_id].parent = nodes[parent_span_id]
        return [node for node in nodes.values() if node.is_root]

    def _analyze(self):
        info = TraceInfo()
        # Find basic metadata
        for span in self._raw_trace:
            info.project_name = info.project_name or get_attribute_value(
                span["resource"]["attributes"],
                key=ResourceAttributes.PROJECT_NAME,
            )
            info.run_id = info.run_id or get_attribute_value(
                span["resource"]["attributes"], key=ResourceAttributes.RUN_ID
            )
            info.specifications_id = info.specifications_id or get_attribute_value(
                span["attributes"], key=EvalAttributes.SPECIFICATIONS_ID
            )
            info.scenario_id = info.scenario_id or get_attribute_value(
                span["attributes"], key=EvalAttributes.SCENARIO_ID
            )
            framework = Framework.from_name(
                get_attribute_value(span["attributes"], key="otel.scope.name")
            )
            if framework != Framework.UNKNOWN:
                info.framework = framework
            if info.is_complete:
                break
        # Find framework
        for span in self._raw_trace:
            if "scope" in span:
                scope = span["scope"]
                if scope["name"] == OpeninferenceInstrumentators.CREWAI:
                    info.framework = Framework.CREWAI
                    break
                elif scope["name"] == OpeninferenceInstrumentators.LANGCHAIN:
                    info.framework = Framework.LANGCHAIN
                    break
        # Find duration
        start_time = min(int(span["startTime"]) for span in self._raw_trace)
        end_time = max(int(span["endTime"]) for span in self._raw_trace)
        info.start_time = start_time
        info.duration = (end_time - start_time) / 1e9
        info.framework = info.framework or Framework.UNKNOWN
        return info

    def get_span_by_id(self, span_id: str):
        try:
            target_span = None
            for span in PreOrderIter(self.root):
                if span.span_id == span_id:
                    target_span = span
                    break
            return target_span
        except KeyError:
            return None

    def __repr__(self):
        representation = ""
        if self.root:
            for pre, fill, node in RenderTree(self.root):
                representation += f"{pre}[{node.kind}] {node}\n"
        else:
            raise ValueError("No root span found!")
        return representation

    def pprint(self):
        print(self.__repr__())

    def model_dump(self) -> Dict[str, Any]:
        exporter = TraceExporter()
        tree = exporter.export(self.root)
        return {
            "trace_id": self.trace_id,
            "trace": tree,
            "info": self.info.model_dump(),
            "metadata": self.metadata,
        }
