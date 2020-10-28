#!/bin/sh
# UDP broadcast relay
#---------------------
# Receives UDP broadcasts to $EXT_BCAST on $PORT.
# Re-broadcasts from $EXT_HOST to $INTERNAL_BROADCAST_IP.
# Replies to $INTERNAL_DEFAULT_ROUTER are relayed from $EXT_HOST back to the source.

# asigra is expected to be started with NAT and VNET. In this case
# INTERNAL_DEFAULT_ROUTER is going to be the address of the epair in the host.

: ${PORT:=4404}
: ${INTERNAL_DEFAULT_ROUTER:=172.16.0.1}
: ${INTERNAL_BROADCAST_IP:=172.16.0.3}

if [ -z "${EXT_HOST}" ]; then
	# If we are unable to find default gateway, let's not start socat as it will fail too
	exit 1
fi

if [ -z "${SOCAT_PEERPORT}" ]; then
	# ext -> int
	exec socat -u -v \
		UDP-RECVFROM:${PORT},bind=${EXT_BCAST},broadcast,fork \
		EXEC:"sh $0"
else
	# int -> ext
	exec socat -v \
		STDIN'!!'UDP-SENDTO:${SOCAT_PEERADDR}:${SOCAT_PEERPORT},bind=${EXT_HOST},sourceport=${PORT},reuseaddr,reuseport \
		UDP-DATAGRAM:${INTERNAL_BROADCAST_IP}:${PORT},bind=${INTERNAL_DEFAULT_ROUTER},broadcast
fi
