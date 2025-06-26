def calculate_args_index(f, audit_callback):
    signature_args = list(f.__code__.co_varnames)[:f.__code__.co_argcount]
    # This must match the order used in `Middleware._call_prepare`
    expected_args = []
    if signature_args and signature_args[0] == 'self':
        expected_args.append('self')
    if pass_app := hasattr(f, '_pass_app'):
        expected_args.append('app')
    # `app` comes before `job` as defined in `Job.__run_body`
    if hasattr(f, '_job'):
        expected_args.append('job')
    if audit_callback:
        expected_args.append('audit_callback')
    if hasattr(f, '_pass_thread_local_storage'):
        expected_args.append('tls')
    if pass_app:
        if f._pass_app['message_id']:
            expected_args.append('message_id')

    if signature_args[:len(expected_args)] != expected_args:
        raise RuntimeError(
            f"Invalid method signature for {f!r}. Its arguments list must start with {', '.join(expected_args)!r}. "
            f"It is {', '.join(signature_args)!r}"
        )

    args_index = len(expected_args)
    if hasattr(f, '_skip_arg'):
        args_index += f._skip_arg
    return args_index
