<%!
    class DirectoryServicePamBase(object):
        def __init__(self, **kwargs):
            self.middleware = kwargs.get('middleware')
            self.pam_mkhomedir = "pam_mkhomedir.so"
            self.pam_ldap = "pam_ldap.so"
            self.pam_winbind = "pam_winbind.so"
            self.pam_krb5 = "pam_krb5.so"

        def safe_call(self, *args):
            try: 
                val = self.middleware.call_sync(*args)
            except:
                val = False
            return val

        def name(self):
            return 'Base'

        def enabled(self):
            return False

        def pam_auth(self):
            return ""

        def pam_account(self):
            return ""

        def pam_session(self):
            return ""

        def pam_password(self):
            return ""
         

    class ActiveDirectoryPam(DirectoryServicePamBase):
        def __init__(self, **kwargs):
            super(ActiveDirectoryPam, self).__init__(**kwargs)

        def name(self):
            return 'ActiveDirectory'

        def enabled(self):
            return self.safe_call('activedirectory.config')['enable']

        def pam_auth(self):
            module = self.pam_winbind
            args = ["try_first_pass", "krb5_auth", "krb5_ccache_type=FILE"]
            module_args = " ".join(args)

            return f"auth\t\tsufficient\t{module}\t{module_args}"

        def pam_account(self):
            module = self.pam_winbind
            args = ["krb5_auth", "krb5_ccache_type=FILE"]
            module_args = " ".join(args)

            return f"account\t\tsufficient\t{module}\t{module_args}"

        def pam_session(self):
            return f"session\t\trequired\t{self.pam_mkhomedir}"

        def pam_password(self):
            module = self.pam_winbind
            args = ["try_first_pass", "krb5_auth", "krb5_ccache_type=FILE"]
            module_args = " ".join(args)

            return f"password\tsufficient\t{module}\t{module_args}"


    class LDAPPam(DirectoryServicePamBase):
        def __init__(self, **kwargs):
            super(LDAPPam, self).__init__(**kwargs)

        def name(self):
            return 'LDAP'

        def enabled(self):
            return self.safe_call('ldap.config')['enable']

        def is_kerberized(self):
            return True if (self.safe_call('ldap.config'))['kerberos_realm'] else False

        def min_uid(self):
            config = self.safe_call('ldap.config')
            min_uid = 1000
            for param in config['auxiliary_parameters'].splitlines():
                param = param.strip()
                if param.startswith('nss_min_uid'):
                    try:
                        override = param.split()[1].strip()
                        if override.isdigit():
                            min_uid = override
                    except Exception:
                        self.middleware.logger.debug(
                            "Failed to override default minimum UID for pam_ldap",
                            exc_info=True
                        )
            return min_uid

        def pam_auth(self):
            module = self.pam_ldap
            min_uid = self.min_uid()
            args = [
                "try_first_pass",
                "ignore_unknown_user",
                "ignore_authinfo_unavail",
                "no_warn",
                f"minimum_uid={min_uid}"
            ]
            krb5_args = ["try_first_pass", "no_warn"]

            module_args = " ".join(args)

            ldap_entry = f"auth\t\tsufficient\t{module}\t{module_args}"
            krb5_entry = f"auth\t\tsufficient\t{self.pam_krb5}\t\t{' '.join(krb5_args)}"
            if self.is_kerberized():
                return f"{krb5_entry}\n{ldap_entry}"
            else:
                return ldap_entry

        def pam_account(self):
            module = self.pam_ldap
            min_uid = self.min_uid()
            args = [
                "try_first_pass",
                "ignore_unknown_user",
                "ignore_authinfo_unavail",
                "no_warn",
                f"minimum_uid={min_uid}"
            ]
            krb5_args = ["no_warn"]

            module_args = " ".join(args)

            ldap_entry = f"account\t\tsufficient\t{module}\t{module_args}"
            krb5_entry = f"account\t\tsufficient\t{self.pam_krb5}\t\t{' '.join(krb5_args)}"
            if self.is_kerberized():
                return f"{krb5_entry}\n{ldap_entry}"
            else:
                return ldap_entry

        def pam_session(self):
            return f"session\t\trequired\t{self.pam_mkhomedir}"

        def pam_password(self):
            module = self.pam_ldap
            min_uid = self.min_uid()
            args = [
                "ignore_unknown_user",
                "ignore_authinfo_unavail",
                "no_warn",
                f"minimum_uid={min_uid}"
            ]
            krb5_args = ["try_first_pass", "no_warn"]

            module_args = " ".join(args)

            ldap_entry = f"password\tsufficient\t{module}\t{module_args}"
            krb5_entry = f"password\t\tsufficient\t{self.pam_krb5}\t\t{' '.join(krb5_args)}"
            if self.is_kerberized():
                return f"{krb5_entry}\n{ldap_entry}"
            else:
                return ldap_entry


    class NISPam(DirectoryServicePamBase):
        def __init__(self, **kwargs):
            super(NISPam, self).__init__(**kwargs)

        def name(self):
            return 'NIS'

        def enabled(self):
            return IS_FREEBSD and self.safe_call('nis.config')['enable']


    class DirectoryServicePam(DirectoryServicePamBase):
        def __new__(cls, **kwargs):
            obj = None

            try:
                if ActiveDirectoryPam(**kwargs).enabled():
                    obj = ActiveDirectoryPam(**kwargs)
                elif LDAPPam(**kwargs).enabled():
                    obj = LDAPPam(**kwargs)
                elif NISPam(**kwargs).enabled():
                    obj = NISPam(**kwargs)
            except Exception as e:
                obj = None

            if not obj:
                obj = DirectoryServicePamBase()

            return obj
%>
<%def name="getDirectoryServicePam(**kwargs)">
  <% return DirectoryServicePam(**kwargs) %>
</%def>
