export PATH ?= /usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

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
	rm -rf build-mw-deb/

build_deb:
	mkdir -p build-mw-deb
	# Ignore the changes file generation error - we only need the .deb file
	dpkg-buildpackage -b -us -uc -nc || true
	# Check if .deb file was created and move it to build directory
	@if DEB_FILE=$$(ls ../middlewared_*.deb 2>/dev/null | head -1) && [ -f "$$DEB_FILE" ]; then \
		mv $$DEB_FILE build-mw-deb/; \
		echo "$$(basename $$DEB_FILE)" > build-mw-deb/.deb_name; \
		echo "Built: $$(basename $$DEB_FILE)"; \
	else \
		echo "Build failed: middlewared_*.deb file not found" >&2; \
		exit 1; \
	fi

install:
	# Install the debian package from build directory
	@if [ -f build-mw-deb/.deb_name ]; then \
		DEB_FILE="build-mw-deb/$$(cat build-mw-deb/.deb_name)"; \
		if [ -f "$$DEB_FILE" ]; then \
			echo "Installing: $$(basename $$DEB_FILE)"; \
			dpkg -i $$DEB_FILE || apt-get install -f -y; \
		else \
			echo "Package file $$DEB_FILE not found" >&2; \
			exit 1; \
		fi; \
	else \
		echo "No .deb_name file found. Run 'make build_deb' first." >&2; \
		exit 1; \
	fi

remove_mako:
	rm -rf /var/run/mako/etc_files

# kept here for backwards compatibility for our internal CI
# and builds that are Goldeye or older. Halfmoon and newer
# dont use this.
install_test:
	bash install-dev-tools
	pip install --no-build-isolation --break-system-packages --root-user-action=ignore .

install_deps:
	bash install-dev-tools

migrate:
	migrate

reinstall: stop_service install_deps clean build_deb remove_mako install migrate start_service

# this is to be called in github actions running in a container (no systemd (pid 1))
# so it's the same as `reinstall` but without the start/stop{_service} and migrate calls
reinstall_container: install_deps clean build_deb install
