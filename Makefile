

# FreeNAS Build Makefile
# Version:  10.0.0

all:
	sh build/do_build.sh -ff

clean:
	rm -rf ./FreeBSD
	rm -rf ./os-base
