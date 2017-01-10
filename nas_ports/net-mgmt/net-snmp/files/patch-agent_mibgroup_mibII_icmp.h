--- agent/mibgroup/mibII/icmp.h.orig	2014-12-08 20:23:22 UTC
+++ agent/mibgroup/mibII/icmp.h
@@ -14,6 +14,8 @@ config_arch_require(freebsd7,  mibII/ker
 config_arch_require(freebsd8,  mibII/kernel_sysctl)
 config_arch_require(freebsd9,  mibII/kernel_sysctl)
 config_arch_require(freebsd10, mibII/kernel_sysctl)
+config_arch_require(freebsd11, mibII/kernel_sysctl)
+config_arch_require(freebsd12, mibII/kernel_sysctl)
 config_arch_require(netbsd,    mibII/kernel_netbsd)
 config_arch_require(netbsdelf, mibII/kernel_netbsd)
 config_arch_require(openbsd4,  mibII/kernel_sysctl)
