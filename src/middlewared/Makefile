clean:
	rm -rf build

reinstall: clean
	rm -rf /usr/local/lib/python3.6/site-packages/middlewared*
	python setup.py install --single-version-externally-managed --record=/dev/null

dev: reinstall
	middlewared restart -L -P --debug-level 'TRACE'

reinstall-remote:
	sh -c 'if [ -z "${HOST}" ]; then echo "You need to set HOST"; exit 1; fi;'
	tar cf - . | ssh root@${HOST} 'cat > /tmp/middleware.tar; set tmpdir=`mktemp -d`; tar xf /tmp/middleware.tar -C $$tmpdir; cd $$tmpdir; make reinstall; service middlewared restart'
