#!/usr/bin/nawk -f
BEGIN { 
#	print ( "hellowworld" ); 
	}

/ses/ { 
	#print ( $1 " found");
	gsub ( /:/,  "", $1)
	lses = $1
	}

/Enclosure Name/ { 
	FS=":"; 
	lencname=$2; 
	#print ("  encname: " lencname ); 
	}

#        Element 4, Type: Array Device Slot
/Element/ {
	FS=" "
	lelt=$2; 
	gsub ( /,/,"", lelt); # dump the ,
	ltype=$4 $5 $6
	}

#                Status: OK (0x01 0x00 0x00 0x00
/Status/ {

	FS=":"
	split ( $2, splitout, " " ); 
	lstatus=splitout[1]
	}
	
#                Description: Disk #0F
/Description/ { 
	FS=":"
	ldesc = $2
 	}

	
#                Device Names: da15,pass16
/Device Names/ {
	FS=":"
	split ( $2, splitout, "," ); 
	if ( match( splitout[1], "da") > 0 )  {
		print (" slot: " ldesc " status: " lstatus  " ses: " lses " disk: " splitout[1]);
	} else {
		print (" slot: " ldesc " status: " lstatus  " ses: " lses " empty: " $2);
		}
	
	}
	
	

END  { 
#print ( "byeo " NR " records found " ); 
}
#
#ses0:
#        Enclosure Name: ECStream 3U16+4R-4X6G.3 d1f8
#        Enclosure ID: 5b0bd6d0a10460bf
#        Element 0, Type: Array Device Slot
#                Status: Unsupported (0x00 0x00 0x00 0x00)
#                Description: SES Array Device
#        Element 1, Type: Array Device Slot
#                Status: OK (0x11 0x00 0x00 0x00)
#                Description: Disk #00
#                Device Names: pass13
#                Extra status:
#                - Swapped
#        Element 2, Type: Array Device Slot
#                Status: OK (0x01 0x00 0x00 0x00)
#                Description: Disk #01
#                Device Names: da1,pass2
#        Element 3, Type: Array Device Slot
#                Status: OK (0x01 0x00 0x00 0x00)
#                Description: Disk #02
#                Device Names: da0,pass1
#        Element 4, Type: Array Device Slot
#                Status: OK (0x01 0x00 0x00 0x00)
#                Description: Disk #03
#                Device Names: da2,pass3
#        Element 5, Type: Array Device Slot
#                Status: OK (0x01 0x00 0x00 0x00)
