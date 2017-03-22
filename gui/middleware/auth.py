from freenasUI.middleware.client import client
from freenasUI.account.models import bsdUsers


class AuthTokenBackend(object):

    def authenticate(self, auth_token=None):
        with client as c:
            rv = c.call('auth.token', auth_token)
            if rv:
                qs = bsdUsers.objects.filter(bsdusr_uid=0)
                if qs.exists():
                    return qs[0]
                else:
                    return None
            return None

    def get_user(self, user_id):
        qs = bsdUsers.objects.filter(bsdusr_uid=0)
        if not qs.exists():
            return None
        return qs[0]
