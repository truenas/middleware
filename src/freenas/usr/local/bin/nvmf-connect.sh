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

  if [ $disconnected -eq 0 ]; then
    counter=0
    local_nqns=$(echo -e "$local_nqns" | tr -s '\n' | sort)

    while [ $counter -lt $RECONNECT_TIMEOUT_SEC ]; do
      connect_nqns=$(nvme discover $args | grep subnqn: | awk '{gsub(/^subnqn: */,"")}1' \
          | tr -s '\n' | sort)

      if [[ -n "$local_nqns" && "$local_nqns" != "$connect_nqns" ]]; then
        break
      fi

      ((counter++))
      sleep 1
    done
  fi

  connect_all=$(nvme connect-all $args)
done
echo "EXIT" > $queue
