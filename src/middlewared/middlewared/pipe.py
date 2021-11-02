import os
import tempfile


class Pipes:
    """
    `job.pipes` object containing job's open pipes. Each pipe is a :class:`middlewared.pipe.Pipe` object.

    :ivar input: Input pipe

    :ivar output: Output pipe
    """
    def __init__(self, input=None, output=None):
        self.input = input
        self.output = output

    def __iter__(self):
        if self.input is not None:
            yield self.input

        if self.output is not None:
            yield self.output

    async def close(self):
        for pipe in self:
            await pipe.close()


class Pipe:
    """
    Job's opened pipe.

    :ivar buffered: Determines whether the pipe is buffered.

        If a pipe is unbuffered (default) then the underlying resource is `os.pipe` object. Pipe writer will block
        if the reader is not reading the pipe. Pipe reader will block until the writer finishes (or explicitly closes
        the pipe).

        If a pipe is buffered then the underlying resource is unbuffered temporary file. Pipe writer can write to the
        pipe at his own cadence and will never block. Pipe reader can read from the pipe and will never block, but if
        it reaches EOF, it does not mean that the writer has already finished writing. Reader must implement another
        method of determining whether it has already consumed all the input (e.g. checking if writer job has
        terminated).

    :ivar r: Reading side of the pipe
    :ivar w: Writing side of the pipe
    """
    def __init__(self, middleware, buffered=False):
        self.middleware = middleware

        if buffered:
            self.w = tempfile.NamedTemporaryFile(buffering=0)
            self.r = open(self.w.name, "rb")
        else:
            r, w = os.pipe()
            self.r = os.fdopen(r, "rb")
            self.w = os.fdopen(w, "wb")

    async def close(self):
        await self.middleware.run_in_thread(self.r.close)
        await self.middleware.run_in_thread(self.w.close)
