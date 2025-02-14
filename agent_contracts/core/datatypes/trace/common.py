from enum import Enum
from typing import Optional
from anytree.node.nodemixin import NodeMixin
from openinference.semconv.trace import SpanAttributes
from agent_contracts.core.utils.trace_attributes import (
    get_attribute_value,
    recreate_attributes_hierarchy,
)
from agent_contracts.core.datatypes.trace.semcov import EvalAttributes

class Framework(Enum):
    CREWAI = "crewai"
    LANGCHAIN = "langchain"
    UNKNOWN = "unknown"

    @classmethod
    def from_name(cls, name: Optional[str] = None):
        if name is None:
            return cls.UNKNOWN
        if "crewai" in name:
            return cls.CREWAI
        elif "langchain" in name:
            return cls.LANGCHAIN
        else:
            return cls.UNKNOWN


class Span(NodeMixin):
    def __init__(
        self,
        span_id: str,
        name: str,
        kind: str,
        attributes: dict,
        start_time: int,  # unix nanoseconds
        end_time: int,  # unix nanoseconds
        parent=None,
        children=None,
        **kwargs,
    ):
        self.__dict__.update(kwargs)
        self.span_id = span_id
        self.name = name
        self.kind = kind
        self.raw_attributes = attributes
        self.start_time = start_time
        self.end_time = end_time
        self.parent = parent
        if children:
            self.children = children
        self._post_init()

    def _post_init(self):
        if get_attribute_value(self.raw_attributes, EvalAttributes.SCENARIO_ID):
            self.kind = "EVAL_START"
        else:
            self.kind = get_attribute_value(
                self.raw_attributes,
                SpanAttributes.OPENINFERENCE_SPAN_KIND,
                "UNKNOWN",
            )
        # Recreate attributes hierarchy from key1.key2.key3...
        self.attributes = recreate_attributes_hierarchy(self.raw_attributes)
        # Postprocess attributes
        self.attributes = {
            k: self._postprocess_attribute(v)
            for k, v in self.attributes.items()
            if "openinference" not in k
        }

    def _postprocess_attribute(self, attribute):
        """
        Simplifies an attribute dictionary.

        If the attribute is not a dictionary, it is returned as is. If it contains
        only 'value' and 'mime_type' keys, the function returns the value of 'value'.
        For other dictionaries, it recursively processes each key-value pair.

        Args:
            attribute (dict): The attribute to process.

        Returns:
            The simplified attribute value or a processed dictionary.
        """
        if not isinstance(attribute, dict):
            return attribute
        if set(attribute.keys()) == {"value", "mime_type"}:
            return attribute["value"]
        else:
            for k, v in attribute.items():
                attribute[k] = self._postprocess_attribute(v)
            return attribute

    def __str__(self):
        return f"{self.name} (spanID: {self.span_id})"

    def to_dict(self):
        return {
            "span_id": self.span_id,
            "name": self.name,
            "kind": self.kind,
            "attributes": self.raw_attributes,
            "start_time": self.start_time,
            "end_time": self.end_time,
        }
