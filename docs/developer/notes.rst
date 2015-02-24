===============
Developer notes
===============

---------------------------
Directory services (DSLite)
---------------------------

* Client side (libc) should attempt IPC and fall-back to flat-file abstraction layer if DSLite is not available yet (or has crashed)
* Flat-file abstraction piece should be in its own library, so both Libc and DSLite Daemon can link with the same code (presumably, this will also influence the design of the abstraction layer’s API)
* Hide implementation details of AD / LDAP / NIS / NT4 / … behind a similar (same?) abstraction layer even if everything is linked into one big address space in DSLiteD.  This will give us freedom to change the back-end implementations over time, even embedding native LDAP/AD libraries directly into the daemon if and when we can obtain them and, by so doing, get better diagnostics / behavior in the process.
* Should use existing interfaces to various directory services, eg. some ldap library, winbindd interface for AD, etc and provide uniform caching
* Should talk with middleware dispatcher using its RPC interface (just like our current etcd or networkd does) so GUI/CLI could read (rich) account and debugging informations directly
* Should contain a PAM module for providing authentication and libnss module for getpw*(), getgr*(), etc implementations. Those things need to talk with the daemon through some IPC. We could reuse standard middleware RPC protocol here.
* Should talk with middleware dispatcher for getting out local user accounts/groups from database
* PAM and libnss modules should have a fallback mechanism if daemon is not reachable. One of the ideas is to use flat JSON files to read account and group information. Other idea is to preserve original /etc/passwd & Co. with default user account data.
* Should emit events back to the middleware with notifications about accounts added/deleted/changed so the GUI could update it’s state in real time
