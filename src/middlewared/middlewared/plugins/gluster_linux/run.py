from glustercli.cli.utils import GlusterCmdException

from middlewared.service import CallError, Service


class GlusterMethodService(Service):

    class Config:
        namespace = 'gluster.method'
        private = True

    def run(self, func, options=None):

        result = b''

        if options is not None:
            args = options.get('args', ())
            kwargs = options.get('kwargs', {})
        else:
            args = ()
            kwargs = {}

        try:
            result = func(*args, **kwargs)
        except GlusterCmdException as e:
            # gluster cli binary will return stderr to stdout
            # and vice versa depending on the failure.
            rc, out, err = e.args[0]
            err = err if err else out
            if isinstance(err, bytes):
                err = err.decode()
            raise CallError(err.strip())
        except Exception:
            raise

        if isinstance(result, bytes):
            return result.decode().strip()

        return result
