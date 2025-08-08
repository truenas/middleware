#!/bin/bash

args="$*"
discovery_dev=$(echo "$args" | grep -oP '(?<=--device=)\w+')
power_recovery_queue="/var/run/${discovery_dev}-power-recovery-queue"

# Default timeout for power recovery (in attempts, ~5s each)
MAX_ATTEMPTS=12
attempt=0

while [ $attempt -lt $MAX_ATTEMPTS ]; do
  # Check queue for reset command
  if [ -s "$power_recovery_queue" ]; then
    command=$(<"$power_recovery_queue")
    if [ "$command" = "RESET" ]; then
      attempt=0
      truncate -s 0 "$power_recovery_queue"
    fi
  fi
  attempt=$((attempt + 1))
  nvme connect-all $args
  sleep 5
done

rm -f "$power_recovery_queue"
