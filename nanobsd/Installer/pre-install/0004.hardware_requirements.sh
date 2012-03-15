#!/bin/sh
#
# Ensure that users meet the minimum hardware requirements, e.g. don't try and
# install the software on unsupported machines.
#
# Put other fun checks (vendor/firmware specific ones) in separate scripts so
# this script doesn't grow too large.
#
# Garrett Cooper, March 2012
#

# We're not talkin the business man's RAM ;)..
GB=$(( 1024*1024*1024 ))

# 1.0GHz
MINIMUM_CPU_REQUIREMENT=1000

# 1GB
MINIMUM_RAM_REQUIREMENT=$(( 1 * $GB ))

# XXX: x86 only
cpufreq=$(sysctl_n machdep.tsc_freq)
if [ "$cpufreq" -lt $MINIMUM_CPU_REQUIREMENT ]
then
	warn "CPU is too slow ($cpufreq < $MINIMUM_CPU_REQUIREMENT)"
fi

# hw.physmem
ram=$(sysctl_n hw.physmem)
if [ $ram -lt $MINIMUM_RAM_REQUIREMENT ]
then
	warn "not enough RAM ($ram < $MINIMUM_RAM_REQUIREMENT)"
fi
