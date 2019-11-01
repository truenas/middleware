import inspect
import linecache
import sys
import traceback
import types


def get_frame_details(frame, logger):

    if not isinstance(frame, types.FrameType):
        return {}

    cur_frame = {
        'filename': frame.f_code.co_filename,
        'lineno': frame.f_lineno,
        'method': frame.f_code.co_name,
        'line': linecache.getline(frame.f_code.co_filename, frame.f_lineno),
    }

    argspec = None
    varargspec = None
    keywordspec = None
    _locals = {}

    try:
        arginfo = inspect.getargvalues(frame)
        argspec = arginfo.args
        if arginfo.varargs is not None:
            varargspec = arginfo.varargs
            temp_varargs = list(arginfo.locals[varargspec])
            for i, arg in enumerate(temp_varargs):
                temp_varargs[i] = '***'

            arginfo.locals[varargspec] = tuple(temp_varargs)

        if arginfo.keywords is not None:
            keywordspec = arginfo.keywords

        _locals.update(list(arginfo.locals.items()))

    except Exception:
        logger.critical('Error while extracting arguments from frames.', exc_info=True)

    if argspec:
        cur_frame['argspec'] = argspec
    if varargspec:
        cur_frame['varargspec'] = varargspec
    if keywordspec:
        cur_frame['keywordspec'] = keywordspec
    if _locals:
        try:
            cur_frame['locals'] = {k: repr(v) for k, v in _locals.items()}
        except Exception:
            # repr() may fail since it may be one of the reasons
            # of the exception
            cur_frame['locals'] = {}
    return cur_frame


def get_threads_stacks():
    return {
        thread_id: traceback.format_stack(frame)
        for thread_id, frame in sys._current_frames().items()
    }
