import asyncio
from collections import defaultdict

from confluent_kafka import Consumer
from loguru import logger

from agent_contracts.certification.config import RuntimeVerificationConfig
from agent_contracts.certification.proto import parse_span
from agent_contracts.certification.workers import certify_span
from agent_contracts.core.utils.trace_attributes import get_attribute_value


def preprocess(span_data: dict):
    spans_by_trace_id = defaultdict(list)
    for resource in span_data["resourceSpans"]:
        x = get_attribute_value(resource["resource"], "service.name")
        if x != "relari-otel":
            continue
        for scope in resource["scopeSpans"]:
            for span in scope["spans"]:
                span["resource"] = resource["resource"]
                span["attributes"].append(
                    {"key": "otel.scope.name", "value": scope["scope"]["name"]}
                )
                spans_by_trace_id[span["traceId"]].append(span)
    return spans_by_trace_id


def main():
    consumer = Consumer(RuntimeVerificationConfig.kafka.to_confluent_config())
    consumer.subscribe([RuntimeVerificationConfig.kafka.topic])
    try:
        logger.info("Waiting for messages, press Ctrl+C to stop.")
        while True:
            msg = consumer.poll(0.05)
            span_data, format_type = parse_span(msg)
            if span_data:
                logger.info(f"Received msg, type: {format_type}")
                spans_by_trace_id = preprocess(span_data)
                for trace_id, spans in spans_by_trace_id.items():
                    asyncio.run(certify_span(trace_id, spans))
    except KeyboardInterrupt:
        logger.info("Quitting...")
    finally:
        consumer.close()


if __name__ == "__main__":
    main()
