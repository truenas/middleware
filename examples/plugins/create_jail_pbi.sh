#!/bin/sh

base=/usr/pbistuff
jaildir=plugins

pbi_create \
-a 'FreeNAS' \
-n plugins_jail \
-o ${base} \
-r 8.2 \
-w 'http://www.freenas.org' \
${jaildir}
