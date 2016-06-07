--- ldap-nss.h.orig
+++ ldap-nss.h
@@ -923,6 +923,8 @@
 int _nss_ldap_get_ld_errno (char **m, char **s);
 
 #ifdef CONFIGURE_KRB5_KEYTAB
-int do_init_krb5_cache(ldap_config_t *config);
+int do_init_krb5_cache (ldap_config_t *config);
+int do_select_krb5_cache (ldap_config_t * config);
+int do_restore_krb5_cache (ldap_config_t * config);
 #endif /* CONFIGURE_KRB5_KEYTAB */
 #endif /* _LDAP_NSS_LDAP_LDAP_NSS_H */
