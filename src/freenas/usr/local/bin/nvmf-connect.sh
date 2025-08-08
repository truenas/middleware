#!/bin/bash

RECONNECT_TIMEOUT_SEC=5

# Reduce number of queues to 16 due to Viking limitation
args=$(echo "$@" | sed -E 's/(-i\s+[0-9]+|--nr-io-queues=[0-9]+)//g') 
args="$args -i 16"

discovery_dev=$(echo "$args" | grep -oP '(?<=--device=)\w+')
discovery_addr=$(</sys/class/nvme/${discovery_dev}/address)
queue="/var/run/${discovery_dev}-fabric-queue"

while [ -s $queue ]; do
  truncate -s 0 $queue
  local_nqns=""
  disconnected=0
  discovery_nqns=$(nvme discover $args | grep subnqn: | awk '{gsub(/^subnqn: */,"")}1')

  for nqn_f in /sys/class/nvme-fabrics/ctl/nvme*/subsysnqn; do
    dev=$(basename "$(dirname "$nqn_f")")
    nqn=$(<"$nqn_f")
    addr=$(</sys/class/nvme/${dev}/address)

    if [[ "$dev" == "$discovery_dev" || "$addr" != "$discovery_addr" ]]; then
      continue
    fi

    if [[ "$discovery_nqns" != *"$nqn"* ]]; then
      nvme disconnect -d $dev
      disconnected=1
    else
      local_nqns+="$nqn"$'\n'
    fi
  done

  # Handle Power Recovery: Detect power restoration scenarios and manage recovery service
  # 
  # During shelf power cycle, after the shelf comes back online, the remote
  # sends a series of discovery change events for all the drives at once.
  # However, discovery change events are sent before the discovery page has
  # entries for the drives, and it takes around 30 seconds for all drives to
  # show properly in the discovery page and become connectable. The previous
  # 5-second timeout was insufficient for full shelves, causing nvme
  # connect-all to execute before all drives were discoverable.
  #
  # Power restoration detection:
  # - If no local NQNs exist and no disconnections occurred: power restored or first device added
  # - If disconnections occurred with no local NQNs and queue has events: power recovery needed
  # - If power recovery service is already active: reset timer for additional drives during recovery
  #
  # The power recovery service attempts connect-all 12 times at 5-second intervals.
  # This provides 60+ seconds total as connect-all execution adds additional time.
  # Multiple connect-all calls are safe when drives are already connected.
  power_recovery_queue="/var/run/${discovery_dev}-power-recovery-queue"
  if [[ -f "$power_recovery_queue" || \
       ($disconnected -eq 1 && -z "$local_nqns" && -s "$queue") || \
       ($disconnected -eq 0 && -z "$local_nqns") ]]; then
    if systemctl is-active --quiet ${discovery_dev}-power-recovery.service; then
      echo "RESET" > $power_recovery_queue
    else
      echo "START" > $power_recovery_queue
      systemd-run --unit=${discovery_dev}-power-recovery.service \
        /bin/bash -c "/usr/local/bin/nvmf-power-recovery.sh $args"
    fi
    continue
  fi

  if [ $disconnected -eq 0 ]; then
    counter=0
    local_nqns=$(echo -e "$local_nqns" | tr -s '\n' | sort)
    while [ $counter -lt $RECONNECT_TIMEOUT_SEC ]; do
      connect_nqns=$(nvme discover $args | grep subnqn: | awk '{gsub(/^subnqn: */,"")}1' \
          | tr -s '\n' | sort)
      if [[ "$local_nqns" != "$connect_nqns" ]]; then
        break
      fi

      ((counter++))
      sleep 1
    done
  fi

  connect_all=$(nvme connect-all $args)
done
echo "EXIT" > $queue
