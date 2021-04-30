VERSION != cat /etc/version


clean:
	rm -rf build

reinstall: clean
	sh -x -c '\
		path=$$(python3 -c "import sys; sys.path = sys.path[1:]; import middlewared; import os; print(os.path.dirname(middlewared.__spec__.origin))"); \
		rm -rf $$path; \
	'
	python3 setup.py install --single-version-externally-managed --record=/dev/null

dev: reinstall run

run:
	middlewared restart --loop-debug -P --debug-level 'TRACE'

reinstall-remote:
	sh -c 'if [ -z "${HOST}" ]; then echo "You need to set HOST"; exit 1; fi;'
	tar cf - . | ssh root@${HOST} 'cat > /tmp/middleware.tar; set tmpdir=`mktemp -d`; tar xf /tmp/middleware.tar -C $$tmpdir; cd $$tmpdir; make reinstall; service middlewared restart'
