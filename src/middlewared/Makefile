clean:
	rm -rf build

reinstall: clean
	rm -rf /usr/local/lib/python3.6/site-packages/middlewared*
	python setup.py install --single-version-externally-managed --record=/dev/null

dev: reinstall
	middlewared -f restart
