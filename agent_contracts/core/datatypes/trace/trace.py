from typing import Any, Dict, List, Optional

from anytree import PreOrderIter, RenderTree
from anytree.exporter import DictExporter
from pydantic import BaseModel

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
    dataset_id: Optional[str] = None
    uuid: Optional[str] = None
    start_time: Optional[int] = None
    duration: Optional[int] = None

    @property
    def is_complete(self):
        return (
            self.project_name is not None
            and self.run_id is not None
            and self.uuid is not None
            and self.dataset_id is not None
            and self.framework is not None
        )


class Trace:
    def __init__(self, trace_id: str, trace: dict, **kwargs):
        self._raw_trace = trace
        self.trace_id: str = trace_id
        self.trace: List[Span] = self._build(trace)
        self.info: TraceInfo = self._analyze()
        self.metadata = kwargs

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
            info.project_name = get_attribute_value(
                span["resource"]["attributes"],
                key="openinference.project.name",
            )
            info.run_id = get_attribute_value(span["resource"]["attributes"], key="eval.run.id")
            info.dataset_id = get_attribute_value(span["attributes"],key="eval.dataset.id" )
            info.uuid = get_attribute_value(span["attributes"], key="eval.uuid")
            framework = Framework.from_name(get_attribute_value(span['attributes'], key="otel.scope.name" ))
            if framework != Framework.UNKNOWN:
                info.framework = framework
            if info.is_complete:
                break
        # Find framework
        for span in self._raw_trace:
            if "scope" in span:
                scope = span["scope"]
                if scope["name"] == "openinference.instrumentation.crewai":
                    info.framework = Framework.CREWAI
                    break
                elif scope["name"] == "openinference.instrumentation.langchain":
                    info.framework = Framework.LANGCHAIN
                    break
        # Find duration
        start_time = min(int(span["startTime"]) for span in self._raw_trace)
        end_time = max(int(span["endTime"]) for span in self._raw_trace)
        info.start_time = start_time
        info.duration = (end_time - start_time) / 1e9
        info.framework = info.framework or Framework.UNKNOWN
        return info

    @property
    def root(self):
        # Return the first root node (assuming a single trace root)
        return self.trace[0]

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
