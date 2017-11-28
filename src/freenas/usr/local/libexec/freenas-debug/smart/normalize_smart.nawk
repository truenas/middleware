#!/usr/bin/nawk -f
#%./fixsmart.nawk dump.txt
#/dev/da5 WD4001FYYG-01SL3:WMC1F1958436 C:22 w:30417 r:39936
#/dev/da4 WD4001FYYG-01SL3:WMC1F1959175 C:23 w:19381 r:22836
#/dev/da3 WD4001FYYG-01SL3:WMC1F1958433 C:23 w:21 r:26
#/dev/da2 WD4001FYYG-01SL3:WMC1F1958134 C:23 w:33637 r:61495
#/dev/da1 WD4001FYYG-01SL3:WMC1F1990828 C:22 w:30015 r:66206
#/dev/da0 ZeusRAM:STM0001955F1 C:27 w:0 r:0


#  
#/dev/da9
($1 ~ /\/dev/) {
	ldev = $1;
	#print ("gotdec: " $1);
	}

($0 ~ /Product/  ) {
	lmo = $2
	#print ("model" lmo)
	}
($0 ~ /^Serial/  ) {
	lsn = $3
	#print ("sn" lsn)
	}

($0 ~ /^Current/  ) {
	ltemp = $4
	}

($0 ~ /^read/  ) {
	ldelayread = $3
	}

( $0 ~ /grown defect/ ) {
	ldefect = $6
}
($0 ~ /^write/  ) {
	ldelaywrite = $3
	print (ldev " " lmo ":" lsn " C:" ltemp " w:"  ldelaywrite " r:" ldelayread " defects:" ldefect)
	}



	
#/dev/da1
#smartctl 6.5 2016-05-07 r4318 [FreeBSD 10.3-STABLE amd64] (local build)
#Copyright (C) 2002-16, Bruce Allen, Christian Franke, www.smartmontools.org
# 
#=== START OF INFORMATION SECTION ===
#Vendor:               WD
#Product:              WD4001FYYG-01SL3
#Revision:             VR07
#Compliance:           SPC-4
#User Capacity:        4,000,787,030,016 bytes [4.00 TB]
#Logical block size:   512 bytes
#Rotation Rate:        7200 rpm
#Form Factor:          3.5 inches
#Logical Unit id:      0x50000c0f01e9bc90
#Serial number:        WMC1F1990828
#Device type:          disk
#Transport protocol:   SAS (SPL-3)
#Local Time is:        Mon Oct  2 09:58:11 2017 EDT
#SMART support is:     Available - device has SMART capability.
#SMART support is:     Enabled
#Temperature Warning:  Enabled
#Read Cache is:        Enabled
#Writeback Cache is:   Disabled
#
#=== START OF READ SMART DATA SECTION ===
#SMART Health Status: OK
#
#Current Drive Temperature:     22 C
#Drive Trip Temperature:        69 C
#
#Manufactured in week 19 of year 2014
#Specified cycle count over device lifetime:  1048576
#Accumulated start-stop cycles:  34
#Specified load-unload count over device lifetime:  1114112
#Accumulated load-unload cycles:  134
#Elements in grown defect list: 0
#
#Error counter log:
#           Errors Corrected by           Total   Correction     Gigabytes    Total
#               ECC          rereads/    errors   algorithm      processed    uncorrected
#           fast | delayed   rewrites  corrected  invocations   [10^9 bytes]  errors
#read:    5393500    66206     68123   5459706      66206     173233.002           0
#write:   3226925    30015     30342   3256940      30015      94112.353           0
#
