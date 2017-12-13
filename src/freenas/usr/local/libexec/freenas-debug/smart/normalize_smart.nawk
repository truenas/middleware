#!/usr/bin/nawk -f

($1 ~ /\/dev/) {
	dev = $1;
	}

($0 ~ /^Vendor:/) {
	vendor = $2;
	}

($0 ~ /^Rotation Rate/) {
	rRate = $3;
	}

($0 ~ /^Product/) {
	model = $2;
	}

($0 ~ /^Serial number/) {
	serial = $3;
	}

($0 ~ /^Current Drive Temperature/) {
	temp = $4;
	}

($0 ~ /^read:/) {
	delayRead = $3;
	}

($0 ~ /^write:/) {
	delayWrite = $3;
	if (defectList > "0" || uncorrRead > "0" || uncorrWrite > "0" || healthStatus != "OK")
		print (dev " " vendor ":" rRate ":" model ":" serial " C:" temp " dR:" delayRead " dW:" delayWrite " dL:" defectList " uR:" uncorrRead " uW:" uncorrWrite " SMART Status:" healthStatus " **!!!**")
	else
		print (dev " " vendor ":" rRate ":" model ":" serial " C:" temp " dR:" delayRead " dW:" delayWrite)
	}

($0 ~ /^Elements/) {
	defectList = $6;
	}

($0 ~ /^SMART Health Status:/) {
	healthStatus = $4
	}

($0 ~ /^read:/) {
	uncorrRead = $8;
	}

($0 ~ /^write:/) {
	uncorrWrite = $8;
	}
