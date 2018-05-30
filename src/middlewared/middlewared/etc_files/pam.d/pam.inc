<%!
    class DirectoryServicePamBase(object):
        def __init__(self, **kwargs):
            self.middleware = kwargs.get('middleware')
            self.pam_mkhomedir = "/usr/local/lib/pam_mkhomedir.so"
            self.pam_sss = "/usr/local/lib/pam_sss.so"
            self.pam_ldap = "/usr/local/lib/pam_ldap.so"
            self.pam_winbind = "/usr/local/lib/pam_winbind.so"

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
            return self.safe_call('notifier.common', 'system', 'activedirectory_enabled') 

        def pam_auth(self):
            module = self.pam_winbind
            args = ["silent", "try_first_pass", "krb5_auth", "krb5_ccache_type=FILE"]
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
            return self.safe_call('notifier.common', 'system', 'ldap_enabled')

        def __anonymous_bind(self):
            return self.safe_call('notifier.common', 'system', 'ldap_anonymous_bind')

        def pam_auth(self):
            module = self.pam_sss
            args = ["ignore_authinfo_unavail", "quiet"]

            if self.__anonymous_bind():
                module = self.pam_ldap
                args = ["use_first_pass", "ignore_unknown_user",
                    "ignore_authinfo_unavail", "no_warn"]

            module_args = " ".join(args)

            return f"auth\t\tsufficient\t{module}\t{module_args}"

        def pam_account(self):
            module = self.pam_sss
            args = ["ignore_authinfo_unavail", "quiet"]

            if self.__anonymous_bind():
                module = self.pam_ldap
                args = ["ignore_unknown_user", "ignore_authinfo_unavail", "no_warn"]

            module_args = " ".join(args)

            return f"account\t\tsufficient\t{module}\t{module_args}"

        def pam_session(self):
            return f"session\t\trequired\t{self.pam_mkhomedir}"

        def pam_password(self):
            module = self.pam_sss
            args = ["use_authtok", "quiet"]

            if self.__anonymous_bind():
                module = self.pam_ldap
                args = ["use_authtok", "ignore_unknown_user",
                    "ignore_authinfo_unavail", "no_warn"]

            module_args = " ".join(args)

            return f"password\tsufficient\t{module}\t{module_args}"


    class NISPam(DirectoryServicePamBase):
        def __init__(self, **kwargs):
            super(NISPam, self).__init__(**kwargs)

        def name(self):
            return 'NIS'

        def enabled(self):
            return self.safe_call('notifier.common', 'system', 'nis_enabled')


    class DCPam(ActiveDirectoryPam):
        def __init__(self, **kwargs):
            super(DCPam, self).__init__(**kwargs)

        def name(self):
            return 'DC'

        def enabled(self):
            return self.safe_call('notifier.common', 'system', 'domaincontroller_enabled')


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
                elif DCPam(**kwargs).enabled():
                    obj = DCPam(**kwargs) 
            except Exception as e:
                obj = None

            if not obj:
                obj = DirectoryServicePamBase()
           
            return obj
%>
<%def name="getDirectoryServicePam(**kwargs)">
  <% return DirectoryServicePam(**kwargs) %>
</%def>
