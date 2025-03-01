#!/usr/bin/env python3
"""
Kafka Message Replayer

This script reads recorded Kafka messages from a file and produces them back to a
Kafka topic, preserving their original binary format.
"""

import argparse
import json
import time

from confluent_kafka import Producer
from loguru import logger


def parse_args():
    parser = argparse.ArgumentParser(
        description="Replay recorded Kafka messages to a topic"
    )
    parser.add_argument(
        "--broker",
        type=str,
        default="localhost:9094",
        help="Kafka broker address (default: localhost:9094)",
    )
    parser.add_argument(
        "--topic",
        type=str,
        default=None,
        help="Kafka topic to produce to (default: original topic from recording)",
    )
    parser.add_argument(
        "--input-file",
        type=str,
        required=True,
        help="Input file containing recorded messages",
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=1.0,
        help="Rate multiplier (1.0 = original rate, 2.0 = twice as fast, default: 1.0)",
    )
    parser.add_argument(
        "--start-from",
        type=int,
        default=0,
        help="Start replaying from this message index (default: 0)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=0,
        help="Number of messages to replay (0 for all, default: 0)",
    )
    return parser.parse_args()


def create_producer(broker):
    return Producer(
        {
            "bootstrap.servers": broker,
        }
    )


def delivery_report(err, msg):
    """Callback invoked on message delivery success or failure"""
    if err is not None:
        logger.error(f"Message delivery failed: {err}")
    else:
        logger.debug(
            f"Message delivered to {msg.topic()} [{msg.partition()}] at offset {msg.offset()}"
        )


def replay_messages(producer, input_file, target_topic, rate, start_from, count):
    logger.info(f"Reading messages from {input_file}")

    # Load messages
    messages = []
    with open(input_file, "r") as f:
        for line in f:
            messages.append(json.loads(line.strip()))

    total_messages = len(messages)
    logger.info(f"Loaded {total_messages} messages from file")

    if start_from > 0:
        if start_from >= total_messages:
            logger.error(
                f"Start index {start_from} exceeds total message count {total_messages}"
            )
            return
        messages = messages[start_from:]
        logger.info(
            f"Starting from message {start_from}, {len(messages)} messages remaining"
        )

    if count > 0:
        messages = messages[:count]
        logger.info(f"Will replay {len(messages)} messages")

    logger.info(f"Replaying at rate multiplier: {rate}x")
    logger.info("Press Ctrl+C to stop replaying")

    # Keep track of timing
    start_time = time.time()
    last_timestamp = None

    try:
        for i, msg_data in enumerate(messages):
            # Get the topic to produce to (use target if specified, otherwise use original topic)
            topic = target_topic or msg_data["topic"]

            # Convert hex string back to bytes
            value = bytes.fromhex(msg_data["value_base64"])

            # Recreate key if it exists
            key = msg_data.get("key")
            if key is not None:
                key = key.encode("utf-8")

            # Recreate headers if they exist
            headers = msg_data.get("headers", [])
            headers = [
                (k, v.encode("utf-8") if v is not None else None) for k, v in headers
            ]

            # Control replay rate based on original message timestamps
            current_timestamp = msg_data.get("timestamp")
            if (
                last_timestamp is not None
                and current_timestamp is not None
                and rate > 0
            ):
                time_diff = (
                    current_timestamp - last_timestamp
                ) / 1000.0  # ms to seconds
                adjusted_diff = time_diff / rate
                if adjusted_diff > 0:
                    time.sleep(adjusted_diff)

            last_timestamp = current_timestamp

            # Produce the message
            producer.produce(
                topic=topic,
                key=key,
                value=value,
                headers=headers,
                callback=delivery_report,
            )

            # Flush every 100 messages to ensure delivery
            if (i + 1) % 100 == 0:
                producer.flush()
                logger.info(f"Replayed {i + 1}/{len(messages)} messages")

        # Final flush to ensure all messages are delivered
        producer.flush()

    except KeyboardInterrupt:
        logger.info("Replay stopped by user")
        producer.flush()

    duration = time.time() - start_time
    logger.info(f"Replayed {len(messages)} messages in {duration:.2f} seconds")


def main():
    args = parse_args()
    logger.info(f"Starting Kafka replayer with broker {args.broker}")

    producer = create_producer(args.broker)

    try:
        replay_messages(
            producer,
            args.input_file,
            args.topic,
            args.rate,
            args.start_from,
            args.count,
        )
        logger.info("Replay completed")
    except Exception as e:
        logger.error(f"Error during replay: {e}")
        producer.flush()


if __name__ == "__main__":
    main()
