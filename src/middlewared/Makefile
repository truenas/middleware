export MWPATH1=/usr/lib/python3/dist-packages/middlewared
export MWPATH2=/usr/local/lib/python3.9/dist-packages/middlewared
export BUILD=$(shell pwd)/build

stop_service:
	systemctl stop middlewared

start_service:
	systemctl restart middlewared

clean:
	rm -rf $(MWPATH1)*
	rm -rf $(MWPATH2)*
	rm -rf $(BUILD)

install:
	python3 setup.py install --single-version-externally-managed --record=/dev/null

install_client:
	python3 setup_client.py install --single-version-externally-managed --record=/dev/null

install_test:
	bash install-dev-tools
	python3 setup_test.py install --single-version-externally-managed --record=/dev/null

migrate:
	migrate

reinstall: stop_service clean install install_client install_test migrate start_service

# this is to be called in github actions running in a container (no systemd (pid 1))
# so it's the same as `reinstall` but without the start/stop{_service} calls
reinstall_container: clean install install_client install_test migrate
