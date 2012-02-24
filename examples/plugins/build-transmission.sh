#!/bin/sh

pbi_makeport \
	-c transmission_pbi \
	-k \
	-o /usr/pbistuff/ \
	--tmpfs \
	net-p2p/transmission-daemon
