#!/usr/bin/env python3
"""
Kafka Message Recorder

This script consumes messages from a Kafka topic and saves them to a file,
preserving their original binary format.
"""

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path

from confluent_kafka import Consumer, KafkaError
from loguru import logger


def parse_args():
    parser = argparse.ArgumentParser(description="Record Kafka messages to a file")
    parser.add_argument(
        "--broker", type=str, default="localhost:9094",
        help="Kafka broker address (default: localhost:9094)"
    )
    parser.add_argument(
        "--topic", type=str, default="jaeger-spans",
        help="Kafka topic to consume from (default: jaeger-spans)"
    )
    parser.add_argument(
        "--group-id", type=str, default="recorder-group",
        help="Consumer group ID (default: recorder-group)"
    )
    parser.add_argument(
        "--output-dir", type=str, default="./kafka_recordings",
        help="Directory to save recordings (default: ./kafka_recordings)"
    )
    parser.add_argument(
        "--max-messages", type=int, default=0,
        help="Maximum number of messages to record (0 for unlimited, default: 0)"
    )
    parser.add_argument(
        "--timeout", type=int, default=300,
        help="Timeout in seconds (default: 300, 0 for unlimited)"
    )
    return parser.parse_args()


def create_consumer(broker, group_id):
    return Consumer({
        "bootstrap.servers": broker,
        "group.id": group_id,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": True,
    })


def record_messages(consumer, topic, output_dir, max_messages, timeout):
    consumer.subscribe([topic])
    
    # Create output directory if it doesn't exist
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Generate output filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_path / f"kafka_recording_{topic}_{timestamp}.jsonl"
    
    logger.info(f"Recording messages from topic '{topic}' to {output_file}")
    logger.info("Press Ctrl+C to stop recording")
    
    count = 0
    start_time = time.time()
    
    try:
        with open(output_file, "w") as f:
            while True:
                if max_messages > 0 and count >= max_messages:
                    logger.info(f"Reached maximum message count ({max_messages})")
                    break
                
                if timeout > 0 and (time.time() - start_time) > timeout:
                    logger.info(f"Reached timeout ({timeout} seconds)")
                    break
                
                msg = consumer.poll(1.0)
                
                if msg is None:
                    continue
                
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        logger.debug("Reached end of partition")
                    else:
                        logger.error(f"Error: {msg.error()}")
                    continue
                
                # Save message with metadata
                message_data = {
                    "key": msg.key().decode('utf-8') if msg.key() else None,
                    "value_base64": msg.value().hex(),  # Store as hex to preserve binary format
                    "topic": msg.topic(),
                    "partition": msg.partition(),
                    "offset": msg.offset(),
                    "timestamp": msg.timestamp()[1],
                    "headers": [(k, v.decode('utf-8') if v else None) for k, v in msg.headers()] if msg.headers() else []
                }
                
                f.write(json.dumps(message_data) + "\n")
                count += 1
                
                if count % 100 == 0:
                    logger.info(f"Recorded {count} messages so far")
    
    except KeyboardInterrupt:
        logger.info("Recording stopped by user")
    
    logger.info(f"Recorded {count} messages to {output_file}")
    return output_file


def main():
    args = parse_args()
    logger.info(f"Starting Kafka recorder with broker {args.broker}, topic {args.topic}")
    
    consumer = create_consumer(args.broker, args.group_id)
    
    try:
        output_file = record_messages(
            consumer, 
            args.topic, 
            args.output_dir, 
            args.max_messages, 
            args.timeout
        )
        logger.info(f"Recording completed. Messages saved to {output_file}")
    finally:
        consumer.close()
        logger.info("Consumer closed")


if __name__ == "__main__":
    main() 