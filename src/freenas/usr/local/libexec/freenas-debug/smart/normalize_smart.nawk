#!/usr/bin/nawk -f

($1 ~ /\/dev/) {
	ldev = $1;
	}

($0 ~ /Product/  ) {
	lmo = $2
	}

($0 ~ /^Serial/  ) {
	lsn = $3
	}

($0 ~ /^Current/  ) {
	ltemp = $4
	}

($0 ~ /^read/  ) {
	ldelayread = $3
	}

($0 ~ /grown defect/ ) {
	ldefect = $6
	}

($0 ~ /^write/  ) {
	ldelaywrite = $3
	}

($0 ~ /^read:/  ) {
	uncorrRead = $8
	}

($0 ~ /^write:/  ) {
	uncorrWrite = $8
	}

($0 ~ /^Elements/  ) {
	defectList = $6
	}

($0 ~ /^SMART Health/  ) {
	healthStatus = $4

	if (defectList || uncorrRead || uncorrWrite || healthStatus != "OK")
		print (ldev " " lmo ":" lsn " C:" ltemp " dW:" ldelaywrite " dR:" ldelayread " uR:" uncorrRead " uW:" uncorrWrite " dL:" defectList " SMART Status:" healthStatus " ****!!!****")
	else
		print (ldev " " lmo ":" lsn " C:" ltemp " dW:" ldelaywrite " dR:" ldelayread " uR:" uncorrRead " uW:" uncorrWrite " dL:" defectList " SMART Status:" healthStatus)
 	}
