from django.conf import settings
from django.contrib.auth.decorators import login_required

def public(f):
    f.__is_public = True
    return f

class RequireLoginMiddleware(object):
    """
    Middleware component that makes every view be login_required
    unless its decorated with @public
    """
    def process_view(self,request,view_func,view_args,view_kwargs):
        if request.path == settings.LOGIN_URL:
            return None
        if hasattr(view_func, '__is_public'):
            return None
        return login_required(view_func)(request,*view_args,**view_kwargs)
