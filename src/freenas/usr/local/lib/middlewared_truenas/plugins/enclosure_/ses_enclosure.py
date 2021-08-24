import subprocess
import pathlib

from middlewared.service import Service, private


class EnclosureService(Service):

    @private
    def get_ses_enclosures(self):
        """
        Return `getencstat` output for all detected enclosures devices.
        """
        output = {}
        cmd = ['getencstat', '-V']
        for ses in pathlib.Path('/dev').iterdir():
            if not ses.name.startswith('ses'):
                continue

            cmd.append(str(ses))

        idx = None
        with subprocess.Popen(cmd, stdout=subprocess.PIPE) as proc:
            while True:
                line = proc.stdout.readline().decode('utf8', 'ignore')
                if not line:
                    break
                elif line.find('Enclosure Name:') != -1:
                    idx = int(line.split(':')[0].split('ses')[-1])
                    # line looks like /dev/ses0: Enclosure Name:...
                    output[idx] = line
                else:
                    # now we just append the line as is
                    output[idx] += line

        return output
