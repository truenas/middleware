import argparse
import logging
import libzfs
import os
import re
import requests
import subprocess
import tempfile
import textwrap
import tqdm


class MiddlewareGDB(object):

    def __init__(self):
        self.logger = logging.getLogger('middlewaregdb')

    def get_dataset(self, name=None):
        zfs = libzfs.ZFS()
        if name is None:
            for pool in zfs.pools:
                if pool.name == 'freenas-boot':
                    continue
                return pool.root_dataset
            raise RuntimeError('no dataset found')
        else:
            return zfs.get_dataset(name)

    def _get_version(self):
        with open('/etc/version', 'r') as f:
            version = f.read().split()[0]

        product, version = version.split('-', 1)
        major = version.split('-')[0].split('.')[0]

        return {
            'major': major,
            'product': product,
            'version': version,
        }

    def debug_symbols_url(self):
        version = self._get_version()
        if version['product'] == 'FreeNAS':
            base_url = f'https://download.freenas.org/{version["major"]}'
            if 'MASTER' in version['version']:
                verdir = f'MASTER/{version["version"].split("-")[-1]}'
            else:
                verdir = version['version']
            dirurl = f'{base_url}/{verdir}/x64/'
            req = requests.get(dirurl)
            if req.status_code != 200:
                raise RuntimeError(f'debug symbols could not be downloaded ({req.status_code}), provide the url')
            reg = re.search(r'href="(?P<debug>.+?\.debug\.txz)"', req.text, re.M)
            if reg is None:
                raise RuntimeError(f'debug symbols file not found in {dirurl}')
            return f'{dirurl}{reg.group("debug")}'
        else:
            raise RuntimeError(f'product {version["product"]} not supported')

    def _download_debug(self, dataset, url):
        filename = url.rsplit('/', 1)[-1]
        path = f'{dataset.mountpoint}/{filename}'

        if os.path.exists(path):
            first_byte = os.path.getsize(path)
        else:
            first_byte = 0

        headers = {}
        r = requests.head(url)
        total_size = int(r.headers.get('content-length', 0))
        if total_size:
            headers['Range'] = f'bytes={first_byte}-{total_size}'

        if first_byte and first_byte == total_size:
            return path

        r = requests.get(url, headers=headers, stream=True)
        content_range = r.headers.get('content-range')
        if content_range:
            initial = int(content_range.split()[1].split('-')[0])
        else:
            initial = 0

        chunk_size = 64 * 1024
        with open(path, 'ab') as f:
            if not initial:
                f.seek(0)
            pbar = tqdm.tqdm(total=total_size, initial=initial, unit='B', unit_scale=True)
            for chunk in r.iter_content(chunk_size):
                f.write(chunk)
                pbar.update(chunk_size)
        return path

    def extract(self, dataset, path):
        subprocess.run(['tar', '-xf', path, '-C', dataset.mountpoint], check=True)

    def run_gdb(self, dataset):

        with open('/var/run/middlewared.pid', 'r') as f:
            daemon_pid = int(f.read().strip())

        proc = subprocess.Popen([
            'pgrep', '-P', str(daemon_pid)
        ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        middlewared_pid = int(proc.communicate()[0].strip())

        with tempfile.TemporaryDirectory() as td:
            with open(f'{td}/.gdbinit', 'w') as f:
                f.write(textwrap.dedent(
                    f"""\
                    set debug-file-directory {dataset.mountpoint}/world
                    define init_python
                    python
                    sys.path.append('/usr/local/share/python-gdb')
                    import libpython
                    end
                    end
                    """
                ))

            proc = subprocess.Popen([
                'gdb',
                f'-cd={td}',
                '-p', str(middlewared_pid),
                '-batch',
                '-ex', 'init_python',
                '-ex', 'thread apply all py-list',
                '-ex', 'thread apply all py-bt',
            ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            output = proc.communicate()[0]

            outfile = tempfile.NamedTemporaryFile(delete=False)
            outfile.write(output)

            rv = {'local': outfile.name}
            try:
                r = requests.post('http://sprunge.us', {
                    'sprunge': output,
                })
                rv['remote'] = r.text.strip()
            except Exception:
                pass
            return rv

    def main(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('-d', '--dataset', help='Dataset to store debug symbols')
        parser.add_argument('-u', '--url', help='URL to download debug symbols tar file')
        parser.add_argument('-sd', '--skip-download', action='store_true', help='Do not download, use existing file')
        args = parser.parse_args()

        dataset = self.get_dataset(name=args.dataset)
        url = args.url
        if not url:
            url = self.debug_symbols_url()

        if not args.skip_download:
            print('Downloading debug symbols file')
            path = self._download_debug(dataset, url)

            print('Extracting file')
            self.extract(dataset, path)

        print('Running gdb')
        rv = self.run_gdb(dataset)
        if 'local' in rv:
            print(f'Local output: {rv["local"]}')
        if 'remote' in rv:
            print(f'Remote output: {rv["remote"]}')


def main():
    MiddlewareGDB().main()


if __name__ == '__main__':
    main()
