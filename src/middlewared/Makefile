stop_service:
	systemctl stop middlewared

start_service:
	systemctl daemon-reload
	systemctl restart middlewared

clean:
	# deb packages install to a different location
	# compared to pip. This removes any remnants
	# of middlewared so we don't have situation of
	# two "middlewared" packages being on disk at
	# same time.
	find /usr -type d \( -path "*/dist-packages/middlewared" -o -path "*/site-packages/middlewared" \) 2>/dev/null | xargs -r rm -rf

install:
	pip install --no-build-isolation --break-system-packages --root-user-action=ignore .
	cp ./debian/middlewared.service /usr/lib/systemd/system/middlewared.service

install_test:
	bash install-dev-tools
	pip install --no-build-isolation --break-system-packages --root-user-action=ignore .

migrate:
	migrate

reinstall: stop_service clean install migrate start_service

# this is to be called in github actions running in a container (no systemd (pid 1))
# so it's the same as `reinstall` but without the start/stop{_service} and migrate calls
# FIXME: install_client is no more
reinstall_container: clean install install_test
