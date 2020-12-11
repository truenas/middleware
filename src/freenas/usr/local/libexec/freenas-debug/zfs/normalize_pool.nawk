#!/usr/bin/nawk -f
#turn zpool status in to useful output

#  pool: zdb-test
($1 ~ /pool:/) {
	lpool = $2;
	#print ("gotpool: " $2);
	}

#cache and log aren't ONLINE; the sadists that wrote zpool status didn't see this coming
($0 ~ /ONLINE|log|cache|REMOVED|OFFLINE|DEGRADED/  ) {
	#bug: needs an entry for every vdev type
	if ( match ( $1, "gptid") || match ($1, "[a]*da[0-9]") || match ($1, "diskid") || match ($2, "OFFLINE") || match ($1, "[[:alnum:]]{8}(-[[:alnum:]]{4}){3}-[[:alnum:]]{12}") )  {
	#            gptid/13377042-b351-11e7-8040-0007432ba650  ONLINE       0     0     0
	# get device ^^^^^^^^                      and      status^^^^
		print ( "disk: " $1  " state: "  $2  " vdev: " lvdv " pool: " lpool " aux: " $5 $6 $7); 
	} else if (match ($1, "mirror") || match ($1, "log") || match ( $1, "cache") || match ($1, "raidz") ){
	#          mirror-0                                      ONLINE       0     0     0
	# pick  vdev ^^^^^
		lvdv = $1
		#print ( "vdev: " lvdv ); 
	} else {
	#print ( "not ??: " $1 ); 
	}
	
}


# Following is zpool status from ZoL
#  pool: scale2
# state: DEGRADED
#status: One or more devices has been taken offline by the administrator.
#	Sufficient replicas exist for the pool to continue functioning in a
#	degraded state.
#action: Online the device using 'zpool online' or replace the device with
#	'zpool replace'.
#  scan: none requested
#config:

#	NAME                                      STATE     READ WRITE CKSUM
#	scale2                                    DEGRADED     0     0     0
#	  mirror-0                                DEGRADED     0     0     0
#	    03887d86-90af-4e47-b414-2cee7ad6244f  ONLINE       0     0     0
#	    15604eef-4bd5-449e-b285-b51302b96cb3  OFFLINE      0     0     0
#
#errors: No known data errors


# Following is zpool status from ZoF
#errors: No known data errors
#
#  pool: test0
# state: ONLINE
#status: Some supported features are not enabled on the pool. The pool can
#	still be used, but some features are unavailable.
#action: Enable all features using 'zpool upgrade'. Once this is done,
#	the pool may no longer be accessible by software that does not support
#	the features. See zpool-features(7) for details.
#  scan: scrub repaired 0 in 0h10m with 0 errors on Sun Sep 17 00:10:41 2017
#config:
#
#	NAME                                            STATE     READ WRITE CKSUM
#	test0                                           ONLINE       0     0     0
#	  mirror-0                                      ONLINE       0     0     0
#	    gptid/620dd98a-1911-11e6-9b9f-74d435cbbed0  ONLINE       0     0     0
#	    gptid/62b2f767-1911-11e6-9b9f-74d435cbbed0  ONLINE       0     0     0
#	  mirror-1                                      ONLINE       0     0     0
#	    gptid/63542fa4-1911-11e6-9b9f-74d435cbbed0  ONLINE       0     0     0
#	    gptid/63f7643a-1911-11e6-9b9f-74d435cbbed0  ONLINE       0     0     0
#	  mirror-2                                      ONLINE       0     0     0
#	    gptid/6498ceb1-1911-11e6-9b9f-74d435cbbed0  ONLINE       0     0     0
#	    gptid/653abcb7-1911-11e6-9b9f-74d435cbbed0  ONLINE       0     0     0
#	logs
#	  gptid/02af7a21-5158-11e7-a230-74d435434327    ONLINE       0     0     0
#	cache
#	  gptid/ad3c8c18-def2-11e6-a989-74d435434327    ONLINE       0     0     0
#
#errors: No known data errors
