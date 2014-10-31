__author__ = 'jceel'

import readline

class MainLoop(object):
    def __init__(self):
        self.cwd = ['__root__']
        self.namespaces = []
        self.connection = None

    def __get_prompt(self):
        return '/'.join(self.cwd) + '> '

    def repl(self):
        readline.parse_and_bind('tab: complete')
        while True:
            line = raw_input().strip()

            if line == '..':
                if len(self.cwd) > 1:
                    del self.cwd[-1]

def main():
    pass

if __name__ == '__main__':
    main()