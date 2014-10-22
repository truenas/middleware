PREFIX ?= /usr/local

install:
    install etc/dispatcher ${PREFIX}/etc/rc.d/
    install etc/middleware.conf /etc/middleware.conf
    install tools/dispatcherd ${PREFIX}/sbin/
    install tools/dispatcherctl ${PREFIX}/sbin/
    install -d ${PREFIX}/lib/dispatcher
    cp -R src/ ${PREFIX}/lib/dispatcher