
NANO_LABEL?=FreeNAS
VERSION?=9.2.0-ALPHA

ENV_SETUP=env NANO_LABEL=${NANO_LABEL} VERSION=${VERSION} 

all:
	[ `id -u` -eq 0 ] || (echo "Sorry, you must be running as root to build this."; exit 1)
	${ENV_SETUP} build/do_build.sh

clean:
	${ENV_SETUP} build/build_cleanup.py

save-build-env:
	${ENV_SETUP} build/save_build.sh

release:
	${ENV_SETUP} build/build_release.sh
