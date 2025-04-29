import os
from queue import Queue
import tempfile
from threading import Lock
import typing


class Pipes:
    """
    `job.pipes` object containing job's open pipes. Each pipe is a :class:`middlewared.pipe.Pipe` object.

    :ivar inputs: :class:`middlewared.pipe.InputPipes` instance

    :ivar output: Output pipe
    """
    def __init__(self, inputs: typing.Optional["InputPipes"] = None, output: typing.Optional["Pipe"] = None):
        self.inputs = inputs
        self.output = output

    @property
    def input(self):
        """
        Shortcut to access the job's first input pipe.

        :return: :class:`middlewared.pipe.Pipe`
        """
        if self.inputs is None:
            return None

        return self.inputs.first_pipe

    async def close(self):
        if self.inputs is not None:
            await self.inputs.close()

        if self.output is not None:
            await self.output.close()


class InputPipes:
    """
    `job.pipes.inputs` object containing job's input pipes.
    """
    def __init__(self, first_pipe: "Pipe"):
        self.first_pipe = first_pipe
        self.pipes_to_close = [first_pipe]
        self.queue = Queue()
        self.iterating_lock = Lock()
        self.iterating = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.queue.put(None)

    def __iter__(self) -> typing.Iterable["Pipe"]:
        """
        :return: job's input pipes one by one.
        """
        with self.iterating_lock:
            if self.iterating:
                raise RuntimeError("Cannot iterate on %r more than once" % self)

            self.iterating = True

        yield self.first_pipe
        # Consume the unread contents so that the HTTP request parser could proceed to the next part
        self.first_pipe.r.read()

        while True:
            item = self.queue.get()
            if item is None:
                break

            yield item
            # Consume the unread contents so that the HTTP request parser could proceed to the next part
            item.r.read()

    def add_pipe(self, pipe: "Pipe"):
        self.queue.put(pipe)
        self.pipes_to_close.append(pipe)

    async def close(self):
        for pipe in self.pipes_to_close:
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
