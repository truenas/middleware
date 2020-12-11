import argparse
import logging
import requests
import subprocess
import sys
import tempfile


class MiddlewareGDB(object):

    def __init__(self):
        self.logger = logging.getLogger('middlewaregdb')

    def install_dbg(self):
        packages = ['python3-dbg', 'python3-dev']
        for p in packages:
            try:
                subprocess.run(['dpkg', '-L', p], capture_output=True, check=True)
            except subprocess.CalledProcessError:
                subprocess.run(['apt', 'install', '-y', p], check=True)

    def run_gdb(self):

        proc = subprocess.Popen(
            ['pgrep', '-o', '-f', 'middlewared'],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        try:
            middlewared_pid = int(proc.communicate()[0].split()[0].strip())
        except Exception:
            print('Failed to find middlewared process', file=sys.stderr)
            sys.exit(1)

        proc = subprocess.Popen([
            'gdb',
            '-p', str(middlewared_pid),
            '-batch',
            '-ex', 'thread apply all py-list',
            '-ex', 'thread apply all py-bt',
        ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        output = proc.communicate()[0]

        outfile = tempfile.NamedTemporaryFile(delete=False)
        outfile.write(output)

        rv = {'local': outfile.name}
        try:
            r = requests.post('http://ix.io', {
                'f:1': output,
            })
            rv['remote'] = r.text.strip()
        except Exception:
            pass
        return rv

    def main(self):
        parser = argparse.ArgumentParser()
        parser.parse_args()

        print('Making sure debug packages are installed')
        self.install_dbg()

        print('Running gdb')
        rv = self.run_gdb()
        if 'local' in rv:
            print(f'Local output: {rv["local"]}')
        if 'remote' in rv:
            print(f'Remote output: {rv["remote"]}')


def main():
    MiddlewareGDB().main()


if __name__ == '__main__':
    main()
