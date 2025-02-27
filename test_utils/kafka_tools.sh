#!/bin/bash
# Kafka Tools - Helper script for recording and replaying Kafka messages

# Set default values
DEFAULT_BROKER="localhost:9094"
DEFAULT_TOPIC="jaeger-spans"
DEFAULT_OUTPUT_DIR="./kafka_recordings"

# Print help information
print_help() {
  echo "Kafka Tools - Helper script for recording and replaying Kafka messages"
  echo ""
  echo "Usage:"
  echo "  $0 record [options]     Record messages from a Kafka topic"
  echo "  $0 replay [options]     Replay recorded messages to a Kafka topic"
  echo "  $0 list                 List available recordings"
  echo "  $0 help                 Show this help message"
  echo ""
  echo "Record options:"
  echo "  --broker <address>      Kafka broker address (default: $DEFAULT_BROKER)"
  echo "  --topic <topic>         Kafka topic to record from (default: $DEFAULT_TOPIC)"
  echo "  --group-id <id>         Consumer group ID (default: recorder-group)"
  echo "  --output-dir <dir>      Directory to save recordings (default: $DEFAULT_OUTPUT_DIR)"
  echo "  --max-messages <num>    Maximum number of messages to record (0 for unlimited)"
  echo "  --timeout <seconds>     Recording timeout in seconds (0 for unlimited)"
  echo ""
  echo "Replay options:"
  echo "  --broker <address>      Kafka broker address (default: $DEFAULT_BROKER)"
  echo "  --topic <topic>         Kafka topic to replay to (default: original topic from recording)"
  echo "  --input-file <file>     Input file containing recorded messages (required)"
  echo "  --rate <multiplier>     Rate multiplier (1.0 = original rate, 2.0 = twice as fast)"
  echo "  --start-from <index>    Start replaying from this message index (default: 0)"
  echo "  --count <num>           Number of messages to replay (0 for all)"
  echo ""
  echo "Examples:"
  echo "  $0 record --topic my-topic --timeout 60"
  echo "  $0 replay --input-file ./kafka_recordings/kafka_recording_my-topic_20230101_120000.jsonl --rate 2.0"
  echo "  $0 list"
}

# List available recordings
list_recordings() {
  echo "Available Kafka recordings:"
  echo ""
  
  if [ ! -d "$DEFAULT_OUTPUT_DIR" ]; then
    echo "No recordings found. Directory '$DEFAULT_OUTPUT_DIR' does not exist."
    return
  fi
  
  recordings=$(find "$DEFAULT_OUTPUT_DIR" -name "kafka_recording_*.jsonl" | sort -r)
  
  if [ -z "$recordings" ]; then
    echo "No recordings found in '$DEFAULT_OUTPUT_DIR'."
    return
  fi
  
  echo "ID | Filename | Topic | Date | Messages"
  echo "---|----------|-------|------|--------"
  
  id=1
  while IFS= read -r file; do
    filename=$(basename "$file")
    # Extract topic and timestamp from filename
    topic=$(echo "$filename" | sed -E 's/kafka_recording_(.+)_[0-9]{8}_[0-9]{6}\.jsonl/\1/')
    date_str=$(echo "$filename" | sed -E 's/kafka_recording_.+_([0-9]{8})_([0-9]{6})\.jsonl/\1 \2/')
    formatted_date=$(date -j -f "%Y%m%d %H%M%S" "$date_str" "+%Y-%m-%d %H:%M:%S" 2>/dev/null || echo "$date_str")
    
    # Count messages in file
    msg_count=$(wc -l < "$file")
    
    echo "$id | $filename | $topic | $formatted_date | $msg_count"
    id=$((id+1))
  done <<< "$recordings"
}

# Record messages
record_messages() {
  # Parse arguments
  broker="$DEFAULT_BROKER"
  topic="$DEFAULT_TOPIC"
  group_id="recorder-group"
  output_dir="$DEFAULT_OUTPUT_DIR"
  max_messages=0
  timeout=300
  
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --broker)
        broker="$2"
        shift 2
        ;;
      --topic)
        topic="$2"
        shift 2
        ;;
      --group-id)
        group_id="$2"
        shift 2
        ;;
      --output-dir)
        output_dir="$2"
        shift 2
        ;;
      --max-messages)
        max_messages="$2"
        shift 2
        ;;
      --timeout)
        timeout="$2"
        shift 2
        ;;
      *)
        echo "Unknown option: $1"
        print_help
        exit 1
        ;;
    esac
  done
  
  echo "Recording messages from topic '$topic' on broker '$broker'"
  echo "Use Ctrl+C to stop recording"
  
  poetry run python3 kafka_recorder.py \
    --broker "$broker" \
    --topic "$topic" \
    --group-id "$group_id" \
    --output-dir "$output_dir" \
    --max-messages "$max_messages" \
    --timeout "$timeout"
}

# Replay messages
replay_messages() {
  # Parse arguments
  broker="$DEFAULT_BROKER"
  topic=""
  input_file=""
  rate=1.0
  start_from=0
  count=0
  
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --broker)
        broker="$2"
        shift 2
        ;;
      --topic)
        topic="$2"
        shift 2
        ;;
      --input-file)
        input_file="$2"
        shift 2
        ;;
      --rate)
        rate="$2"
        shift 2
        ;;
      --start-from)
        start_from="$2"
        shift 2
        ;;
      --count)
        count="$2"
        shift 2
        ;;
      *)
        echo "Unknown option: $1"
        print_help
        exit 1
        ;;
    esac
  done
  
  if [ -z "$input_file" ]; then
    echo "Error: --input-file is required"
    print_help
    exit 1
  fi
  
  if [ ! -f "$input_file" ]; then
    echo "Error: Input file '$input_file' not found"
    exit 1
  fi
  
  topic_arg=""
  if [ ! -z "$topic" ]; then
    topic_arg="--topic $topic"
  fi
  
  echo "Replaying messages from file '$input_file' to broker '$broker'"
  echo "Use Ctrl+C to stop replaying"
  
  poetry run python3 kafka_replayer.py \
    --broker "$broker" \
    $topic_arg \
    --input-file "$input_file" \
    --rate "$rate" \
    --start-from "$start_from" \
    --count "$count"
}

# Main script execution
case "$1" in
  record)
    shift
    record_messages "$@"
    ;;
  replay)
    shift
    replay_messages "$@"
    ;;
  list)
    list_recordings
    ;;
  help)
    print_help
    ;;
  *)
    print_help
    exit 1
    ;;
esac 