import sys


class Struct:
    """
    Simpler wrapper to access using object attributes instead of keys.
    This is meant for compatibility when switch scripts to use middleware
    client instead of django directly.
    """

    def __init__(self, mapping):
        for k, v in mapping.items():
            if isinstance(v, dict):
                setattr(self, k, Struct(v))
            else:
                setattr(self, k, v)


class ProgressBar(object):
    def __init__(self):
        self.message = None
        self.percentage = 0
        self.write_stream = sys.stderr
        self.used_flag = False
        self.extra = None

    def __enter__(self):
        return self

    def draw(self):
        progress_width = 40
        filled_width = int(self.percentage * progress_width)
        self.write_stream.write('\033[2K\033[A\033[2K\r')
        self.write_stream.write(
            f'Status: {(self.message or "(none)").strip()}' + (
                f' Extra: {self.extra}' if self.extra else ''
            ) + '\n'
        )
        self.write_stream.write(
            'Total Progress: [{}{}] {:.2%}'.format(
                '#' * filled_width, '_' * (progress_width - filled_width), self.percentage
            )
        )
        self.write_stream.flush()

    def update(self, percentage=None, message=None):
        if not self.used_flag:
            self.write_stream.write('\n')
            self.used_flag = True
        if percentage:
            self.percentage = float(percentage / 100.0)
        if message:
            self.message = message
        self.draw()

    def finish(self):
        self.percentage = 1

    def __exit__(self, type, value, traceback):
        if self.used_flag:
            self.draw()
            self.write_stream.write('\n')
