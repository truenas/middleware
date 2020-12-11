#!/usr/bin/nawk -f
# cat tmp/pool.normal | ./join_pool.nawk

/disk:/ {
	FS=":"
	split ($2, splout, " ") 
	ldiskdev=splout[1]
	#toss crypot
	gsub (/.eli/ , "", ldiskdev);
	islinux_code=system("uname -s | grep -q 'Linux'")
	grepsuccess=sprintf("grep %s /tmp/glabel.out", ldiskdev) | getline sesline
	if ( grepsuccess )  {
		split (sesline, sessplit , " " )
		if ( islinux_code == 0 ) {
			rdiskdev=sessplit[1]
			if ( match(rdiskdev, /nvme/) ) {
				gsub (/p[0-9]+/,"", rdiskdev);
			} else {
				gsub (/[0-9]/,"", rdiskdev);
			}
		} else {
			rdiskdev=sessplit[3]
			gsub (/p[0-9]/,"", rdiskdev);
		}
		print ( "/dev: " rdiskdev " " $0); 
		} else {
			#print " 5: " $5 " 6: " $6 " 7: "$7;	
			#resuce the gpid for a an offline disk 
			if ( match ($6, "gptid") ){
				ldiskdev = $6
				gsub ( /0was\/dev\//	, "" , ldiskdev); 
				grepsuccess="grep " ldiskdev  " /tmp/glabel.out " | getline sesline
				if ( grepsuccess )  {
					split (sesline, sessplit , " " ) 
					rdiskdev=sessplit[3]
					gsub (/p[0-9]/,"", rdiskdev);
					print ( "/dev: " rdiskdev " " $0); 
				}
	
			
				
			} else { 
			#no label; print somthing
			print ("noglabel: " $0);	
			}
		}
	}
#disk: ada0p2 state: ONLINE vdev: mirror-0 pool: freenas-boot
#disk: ada1p2 state: ONLINE vdev: mirror-0 pool: freenas-boot
#disk: gptid/620dd98a-1911-11e6-9b9f-74d435cbbed0 state: ONLINE vdev: mirror-0 pool: test0
#disk: gptid/62b2f767-1911-11e6-9b9f-74d435cbbed0 state: ONLINE vdev: mirror-0 pool: test0
#disk: gptid/63542fa4-1911-11e6-9b9f-74d435cbbed0 state: ONLINE vdev: mirror-1 pool: test0
#disk: gptid/63f7643a-1911-11e6-9b9f-74d435cbbed0 state: ONLINE vdev: mirror-1 pool: test0
#disk: gptid/6498ceb1-1911-11e6-9b9f-74d435cbbed0 state: ONLINE vdev: mirror-2 pool: test0
#disk: gptid/653abcb7-1911-11e6-9b9f-74d435cbbed0 state: ONLINE vdev: mirror-2 pool: test0
#disk: gptid/02af7a21-5158-11e7-a230-74d435434327 state: ONLINE vdev: logs pool: test0
#disk: 2035137008960679854 state: OFFLINE vdev: cache pool: test0
#:
#:
#                                      Name  Status  Components
#gptid/1d2373cd-c26f-11e5-a469-74d435434327     N/A  ada0p1
#gptid/1d38f7a3-c26f-11e5-a469-74d435434327     N/A  ada1p1
#gptid/653abcb7-1911-11e6-9b9f-74d435cbbed0     N/A  da7p1
#gptid/6498ceb1-1911-11e6-9b9f-74d435cbbed0     N/A  da6p1
#gptid/63f7643a-1911-11e6-9b9f-74d435cbbed0     N/A  da5p1
#gptid/63542fa4-1911-11e6-9b9f-74d435cbbed0     N/A  da4p1
#gptid/62b2f767-1911-11e6-9b9f-74d435cbbed0     N/A  da3p1
#gptid/620dd98a-1911-11e6-9b9f-74d435cbbed0     N/A  da2p1
#gptid/ad3c8c18-def2-11e6-a989-74d435434327     N/A  da1p1
#gptid/02af7a21-5158-11e7-a230-74d435434327     N/A  da0p1
