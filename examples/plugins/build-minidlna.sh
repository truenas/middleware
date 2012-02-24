#!/bin/sh

pbi_makeport \
	-c minidlna_pbi \
	-k \
	-o /usr/pbistuff/ \
	--tmpfs \
	net/minidlna
