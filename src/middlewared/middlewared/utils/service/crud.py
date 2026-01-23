from typing import Any, Callable

__all__ = ['real_crud_method']


def real_crud_method(method: Callable[..., Any]) -> Callable[..., Any] | None:
    if method.__name__ in ['create', 'update', 'delete'] and hasattr(method, '__self__'):
        child_method: Callable[..., Any] | None = getattr(method.__self__, f'do_{method.__name__}', None)
        if child_method is not None:
            return child_method
    return None
