import json

from confluent_kafka import KafkaError
from google.protobuf.json_format import MessageToDict
from loguru import logger
from opentelemetry.proto.logs.v1.logs_pb2 import LogsData
from opentelemetry.proto.metrics.v1.metrics_pb2 import MetricsData
from opentelemetry.proto.trace.v1.trace_pb2 import TracesData, ResourceSpans, ScopeSpans, Span


def _parse_otlp_proto(raw_data):
    """Try to parse data as different OTLP protobuf types"""
    # Try as Traces
    try:
        traces = TracesData()
        traces.ParseFromString(raw_data)
        return {"type": "traces", "data": MessageToDict(traces)}
    except Exception:
        pass

    # Try as ResourceSpans
    try:
        resource_spans = ResourceSpans()
        resource_spans.ParseFromString(raw_data)
        # Wrap in the structure expected by the consumer
        return {"type": "resource_spans", "data": {"resourceSpans": [MessageToDict(resource_spans)]}}
    except Exception:
        pass
        
    # Try as ScopeSpans
    try:
        scope_spans = ScopeSpans()
        scope_spans.ParseFromString(raw_data)
        # Wrap in the structure expected by the consumer
        return {"type": "scope_spans", "data": {"resourceSpans": [{"scopeSpans": [MessageToDict(scope_spans)]}]}}
    except Exception:
        pass
        
    # Try as individual Span
    try:
        span = Span()
        span.ParseFromString(raw_data)
        # Wrap in the structure expected by the consumer
        return {"type": "span", "data": {"resourceSpans": [{"scopeSpans": [{"spans": [MessageToDict(span)]}]}]}}
    except Exception:
        pass

    # Try as Metrics
    try:
        metrics = MetricsData()
        metrics.ParseFromString(raw_data)
        return {"type": "metrics", "data": MessageToDict(metrics)}
    except Exception:
        pass

    # Try as Logs
    try:
        logs = LogsData()
        logs.ParseFromString(raw_data)
        return {"type": "logs", "data": MessageToDict(logs)}
    except Exception:
        pass

    raise ValueError("Failed to parse as any known OTLP protobuf format")


def parse_span(msg):
    """Parse a span from a message"""
    if msg is None:
        return None, None
        
    if msg.error():
        if msg.error().code() == KafkaError._PARTITION_EOF:
            logger.info("Reached end of partition")
        else:
            logger.error(f"Error: {msg.error()}")
        return None, None
        
    raw_data = msg.value()
    span_data = None
    format_type = "unknown"

    # 1. Try JSON
    try:
        span_data = json.loads(raw_data.decode("utf-8"))
        format_type = "json"
    except (UnicodeDecodeError, json.JSONDecodeError):
        # 2. Try OTLP Protobuf
        try:
            result = _parse_otlp_proto(raw_data)
            span_data = result["data"]
            format_type = f"otlp_{result['type']}"
        except Exception as e:
            # logger.error(f"Failed to parse message: {str(e)}")
            return None, None
            
    return span_data, format_type
