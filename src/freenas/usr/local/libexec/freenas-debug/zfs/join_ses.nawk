#!/usr/bin/nawk -f
#cat tmpfiles/ses.normal | ./join_ses.nawk

# slot:  Disk #02 status: OK ses: ses0 disk:  da0
# -or-
# slot:  Disk #00 status: OK ses: ses0 empty:  pass13
# ses devices must be ' da'
/disk/ {
	FS=":"
	ldiskdev = $5
	#get the leaf vdev from the gptlabel output
	#BUG:worst join ever; this is n^2 for disk count , meh. 
	#Should be in the working set.; don't replace the file with the pipe implemenation
	grepsuccess="grep " ldiskdev  " /tmp/glabel.out  | grep ' da'" | getline sesline
	if ( grepsuccess ) {
		split (sesline, sessplit , " " )
		vdev_leaf = sessplit[1]
		# check for pool membership of the leaf device
		grepleafsuccess="grep " vdev_leaf  " /tmp/pool.normal" | getline poolline	
		if ( grepleafsuccess ) { 
			print  $0 " " poolline
		} else 	 {
			print  $0 " " vdev_leaf " no_pool"
		}
	sesline=""
	ldiskdev=""
	}
	
}

### input
##ses.normal:
# slot:  Disk #00 status: OK ses: ses0 empty:  pass13
# slot:  Disk #01 status: OK ses: ses0 disk:  da1
# slot:  Disk #02 status: OK ses: ses0 disk:  da0
# slot:  Disk #03 status: OK ses: ses0 disk:  da2
# slot:  Disk #04 status: OK ses: ses0 disk:  da3
# slot:  Disk #05 status: OK ses: ses0 disk:  da4
# slot:  Disk #06 status: OK ses: ses0 disk:  da5
# slot:  Disk #07 status: OK ses: ses0 disk:  da6
# slot:  Disk #08 status: OK ses: ses0 disk:  da8
# slot:  Disk #09 status: OK ses: ses0 disk:  da7
# slot:  Disk #0A status: OK ses: ses0 disk:  da9
# slot:  Disk #0B status: OK ses: ses0 disk:  da10
# slot:  Disk #0C status: OK ses: ses0 disk:  da11
# slot:  Disk #0D status: OK ses: ses0 disk:  da13
# slot:  Disk #0E status: OK ses: ses0 disk:  da14
# slot:  Disk #0F status: OK ses: ses0 disk:  da15
##pool.normal
#disk: gptid/2629bd17-4ae4-11e7-87a1-fcaa14e9ea1c state: ONLINE vdev: mirror-0 pool: Palantiri
#disk: gptid/26abd124-4ae4-11e7-87a1-fcaa14e9ea1c state: ONLINE vdev: mirror-0 pool: Palantiri
#disk: gptid/272a8318-4ae4-11e7-87a1-fcaa14e9ea1c state: ONLINE vdev: mirror-1 pool: Palantiri
#disk: gptid/b46c6608-5616-11e7-8e16-0007432933d0 state: ONLINE vdev: mirror-1 pool: Palantiri
#disk: gptid/a610f4bf-811d-11e7-b3eb-0007432ba650 state: ONLINE vdev: mirror-2 pool: Palantiri
#disk: gptid/28b89633-4ae4-11e7-87a1-fcaa14e9ea1c state: ONLINE vdev: mirror-2 pool: Palantiri
#disk: gptid/293f6571-4ae4-11e7-87a1-fcaa14e9ea1c state: ONLINE vdev: mirror-3 pool: Palantiri
#disk: gptid/6cc33737-7c83-11e7-8b44-0007432933d0 state: ONLINE vdev: mirror-3 pool: Palantiri
#disk: ada0p2 state: ONLINE vdev: mirror-0 pool: freenas-boot
#disk: ada1p2 state: ONLINE vdev: mirror-0 pool: freenas-boot
#disk: gptid/13377042-b351-11e7-8040-0007432ba650 state: ONLINE vdev: mirror-0 pool: zdb-test
#disk: gptid/13e82d5b-b351-11e7-8040-0007432ba650 state: ONLINE vdev: mirror-0 pool: zdb-test
