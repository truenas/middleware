__all__ = ['real_crud_method']


def real_crud_method(method):
    if method.__name__ in ['create', 'update', 'delete'] and hasattr(method, '__self__'):
        child_method = getattr(method.__self__, f'do_{method.__name__}', None)
        if child_method is not None:
            return child_method
