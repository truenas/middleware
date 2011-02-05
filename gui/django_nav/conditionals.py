def user_is_authenticated(context, *args, **kwargs):
    return context['user'].is_authenticated()

def user_is_staff(context, *args, **kwargs):
    return context['user'].is_staff

def user_has_perm(context, *args, **kwargs):
    perm = kwargs.pop('perm', args[0] if len(args) else None)
    return context['user'].has_perm(perm)