<%!
    class DirectoryServicePamBase(object):
        def __init__(self, **kwargs):
            self.middleware = kwargs.get('middleware')
            self.pam_mkhomedir = "pam_mkhomedir.so"
            self.pam_ldap = "pam_ldap.so"
            self.pam_winbind = "pam_winbind.so"
            self.pam_krb5 = "pam_krb5.so"
            self.pam_unix = "pam_unix.so"
            self.render_ctx = kwargs.get("render_ctx")

        def base_control(self, success=1, default='ignore', **kwargs):
            out = {'success': success} | (kwargs | {'default': default})
            return [f'{key}={val}' for key, val in out.items()]

        def name(self):
            return 'Base'

        def enabled(self):
            return False

        def generate_pam_line(self, pam_type, pam_control, pam_path, pam_args=None):
            return '\t'.join([
                pam_type,
                f'[{" ".join(pam_control)}]',
                pam_path,
                ' '.join(pam_args or [])
            ])

        def pam_auth(self, **kwargs):
            pam_path = kwargs.pop('pam_path', self.pam_unix)
            pam_args = kwargs.pop('pam_args', None)
            pam_control = self.base_control(**kwargs)

            return self.generate_pam_line(
                'auth',
                pam_control,
                pam_path,
                pam_args
            )

        def pam_account(self, **kwargs):
            pam_path = kwargs.pop('pam_path', self.pam_unix)
            pam_args = kwargs.pop('pam_args', None)
            pam_control = self.base_control(**(kwargs | {'new_authtok_reqd': 'done'}))

            return self.generate_pam_line(
                'account',
                pam_control,
                pam_path,
                pam_args
            )

        def pam_session(self, **kwargs):
            module = self.pam_unix
            return f"session\trequired\t{module}"

        def pam_password(self, **kwargs):
            pam_path = kwargs.pop('pam_path', self.pam_unix)
            pam_args = kwargs.pop('pam_args', [
                'use_authtok',
                'try_first_pass',
                'obscure',
                'sha512',
            ])
            pam_control = self.base_control(**kwargs)

            return self.generate_pam_line(
                'password',
                pam_control,
                pam_path,
                pam_args
            )

    class ActiveDirectoryPam(DirectoryServicePamBase):
        def __init__(self, **kwargs):
            super(ActiveDirectoryPam, self).__init__(**kwargs)

        def name(self):
            return 'ActiveDirectory'

        def enabled(self):
            config = self.render_ctx['activedirectory.config']
            if config['restrict_pam']:
                return False

            return config['enable']

        def pam_auth(self):
            args = ["try_first_pass", "try_authtok", "krb5_auth"]

            unix_auth = super().pam_auth(success=2)
            this_auth = super().pam_auth(pam_path=self.pam_winbind, success=1, pam_args=args)
            return "\n".join([unix_auth, this_auth])

        def pam_account(self):
            args = ["krb5_auth", "krb5_ccache_type=FILE"]

            unix_account = super().pam_account(success=2)
            wb_account = super().pam_account(pam_path=self.pam_winbind, success=1, pam_args=args)
            return "\n".join([unix_account, wb_account])

        def pam_session(self):
            unix_session = super().pam_session()
            return f"{unix_session}\nsession\t\trequired\t{self.pam_mkhomedir}"

        def pam_password(self):
            args = ["try_first_pass", "krb5_auth", "krb5_ccache_type=FILE"]

            unix_passwd = super().pam_password(success=2)
            wb_passwd = super().pam_password(success=1, pam_path=self.pam_winbind, pam_args=args)
            return "\n".join([unix_passwd, wb_passwd])


    class LDAPPam(DirectoryServicePamBase):
        def __init__(self, **kwargs):
            super(LDAPPam, self).__init__(**kwargs)

        def name(self):
            return 'LDAP'

        def enabled(self):
            return self.render_ctx['ldap.config']['enable']

        def is_kerberized(self):
            return True if self.render_ctx['ldap.config']['kerberos_realm'] else False

        def min_uid(self):
            config = self.render_ctx['ldap.config']
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
            min_uid = self.min_uid()

            ldap_args = [
                "try_first_pass",
                "ignore_unknown_user",
                "ignore_authinfo_unavail",
                "no_warn",
                f"minimum_uid={min_uid}"
            ]
            krb5_args = ["try_first_pass", "no_warn", f'minimum_uid={min_uid}']

            unix_entry = super().pam_auth(success=2)
            ldap_entry = super().pam_auth(pam_path=self.pam_ldap, success=1, pam_args=ldap_args)

            entries = [unix_entry, ldap_entry]
            if self.is_kerberized():
                krb5_entry = super().pam_auth(pam_path=self.pam_krb5, success=3, pam_args=krb5_args)
                entries.insert(0, krb5_entry)

            return "\n".join(entries)

        def pam_account(self):
            min_uid = self.min_uid()
            ldap_args = [
                "try_first_pass",
                "ignore_unknown_user",
                "ignore_authinfo_unavail",
                "no_warn",
                f"minimum_uid={min_uid}"
            ]
            krb5_args = ["no_warn", f"minimum_uid={min_uid}"]

            unix_entry = super().pam_account()
            ldap_entry = super().pam_account(success="ok", pam_path=self.pam_ldap, pam_args=ldap_args)

            entries = [unix_entry, ldap_entry]

            if self.is_kerberized():
                krb5_entry = f"account\t\tsufficient\t{self.pam_krb5}\t\t{' '.join(krb5_args)}"
                entries.insert(1, krb5_entry)

            return "\n".join(entries)

        def pam_session(self):
            unix_session = super().pam_session()
            return f"{unix_session}\nsession\t\trequired\t{self.pam_mkhomedir}"

        def pam_password(self):
            min_uid = self.min_uid()
            ldap_args = [
                "ignore_unknown_user",
                "ignore_authinfo_unavail",
                "no_warn",
                f"minimum_uid={min_uid}"
            ]
            krb5_args = ["try_first_pass", "no_warn", f"minimum_uid={min_uid}"]

            unix_entry = super().pam_password(success=2)
            ldap_entry = super().pam_password(pam_path=self.pam_ldap, pam_args=ldap_args, success=1)

            if self.is_kerberized():
                krb5_entry = super().pam_password(pam_path=self.pam_krb5, pam_args=krb5_args, success=3)
                entries.insert(0, krb5_entry)

            entries = [unix_entry, ldap_entry]
            return "\n".join(entries)

    class DirectoryServicePam(DirectoryServicePamBase):
        def __new__(cls, **kwargs):
            obj = None

            try:
                if ActiveDirectoryPam(**kwargs).enabled():
                    obj = ActiveDirectoryPam(**kwargs)
                elif LDAPPam(**kwargs).enabled():
                    obj = LDAPPam(**kwargs)
            except Exception:
                obj = None

            if not obj:
                obj = DirectoryServicePamBase()

            return obj
%>
<%def name="getDirectoryServicePam(**kwargs)">
  <% return DirectoryServicePam(**kwargs) %>
</%def>
