from subprocess import run, PIPE

from pyudev import Context

from middlewared.service import private, Service


class EnclosureService(Service):

    @private
    def list_ses_enclosures(self):
        ctx = Context()
        return [f'/dev/bsg/{i.sys_name}' for i in ctx.list_devices(subsystem='enclosure')]

    @private
    def get_ses_enclosures(self):
        output = {}
        opts = {'encoding': 'utf-8', 'errors': 'ignore', 'stdout': PIPE, 'stderr': PIPE}
        for i, name in enumerate(self.list_ses_enclosures()):
            p = run(["sg_ses", "--page=cf", name], **opts)
            if p.returncode != 0:
                self.logger.warning("Error querying enclosure configuration page %r: %s", name, p.stderr)
                continue
            else:
                cf = p.stdout

            p = run(["sg_ses", "-i", "--page=es", name], **opts)
            if p.returncode != 0:
                self.logger.debug("Error querying enclosure status page %r: %s", name, p.stderr)
                continue
            else:
                es = p.stdout

            output[i] = (name.removeprefix('/dev/'), (cf, es))

        return output
