diff --git a/net-mgmt/net-snmp/files/patch-snmplib__int64.c b/net-mgmt/net-snmp/files/patch-snmplib__int64.c
new file mode 100644
index 0000000..ef34758
--- /dev/null
+++ b/net-mgmt/net-snmp/files/patch-snmplib__int64.c
@@ -0,0 +1,12 @@
+--- snmplib/int64.c
++++ snmplib/int64.c
+@@ -367,7 +367,8 @@ netsnmp_c64_check32_and_update(struct counter64 *prev_val, struct counter64 *new
+          * check wrap incremented high, so reset it. (Because having
+          * high set for a 32 bit counter will confuse us in the next update).
+          */
+-        netsnmp_assert(1 == new_val->high);
++        if (1 != new_val->high)
++            DEBUGMSGTL(("c64", "error expanding to 64 bits: new_val->high != 1"));
+         new_val->high = 0;
+     }
+     else if (64 == rc) {
