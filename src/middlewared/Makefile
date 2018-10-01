VERSION != cat /etc/version


clean:
	rm -rf build

reinstall: clean
	rm -rf /usr/local/lib/python3.7/site-packages/middlewared*
	python setup.py install --single-version-externally-managed --record=/dev/null

dev: reinstall
.if ${VERSION:MTrueNAS*}
	middlewared restart --loop-debug -P -o /usr/local/lib/middlewared_truenas --debug-level 'TRACE'
.else
	middlewared restart --loop-debug -P --debug-level 'TRACE'
.endif

reinstall-remote:
	sh -c 'if [ -z "${HOST}" ]; then echo "You need to set HOST"; exit 1; fi;'
	tar cf - . | ssh root@${HOST} 'cat > /tmp/middleware.tar; set tmpdir=`mktemp -d`; tar xf /tmp/middleware.tar -C $$tmpdir; cd $$tmpdir; make reinstall; service middlewared restart'
