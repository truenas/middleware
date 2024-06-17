#!/bin/bash

if [ "$#" -eq 0 ]; then
  echo "Error: No arguments provided."
  exit 1
fi

discovery_nqn="nqn.2014-08.org.nvmexpress.discovery"
discovery_dev=$(echo "$@" | grep -oP '(?<=--device=)\w+')

if [[ $(</sys/class/nvme/${discovery_dev}/subsysnqn) != $discovery_nqn ]]; then
  echo "Error: Event not on discovery controller"
  exit 1
fi

queue="/var/run/${discovery_dev}-fabric-queue"
echo "QUEUE" > $queue
systemd-run --unit=${discovery_dev}-of.service /bin/bash -c "/usr/local/bin/nvmf-connect.sh $*"

# If service is still active and queue reads EXIT, we have a race. Wait for small interval since
# we already know that nvmf-connect.sh is about to exit.
if [ $? != 0 ] && [ "EXIT" = $(<$queue) ]; then
  sleep 0.1
  systemd-run --unit=${discovery_dev}-of.service /bin/bash -c "/usr/local/bin/nvmf-connect.sh $*"

  if [ $? != 0 ]; then
    echo "Error: ${discovery_dev}-of.service failed to start after waiting for 100 milliseconds"
  fi
fi
