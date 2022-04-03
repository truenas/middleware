import collections
import re

from middlewared.schema import accepts, Dict, returns
from middlewared.service import private, Service


class SystemGeneralService(Service):

    KBDMAP_CHOICES = None

    class Config:
        namespace = 'system.general'
        cli_namespace = 'system.general'

    @accepts()
    @returns(Dict('kbdmap_choices', additional_attrs=True))
    async def kbdmap_choices(self):
        """
        Returns kbdmap choices.
        """
        if not self.KBDMAP_CHOICES:
            self.KBDMAP_CHOICES = await self.middleware.call('system.general.read_kbdmap_choices')
        return self.KBDMAP_CHOICES

    @private
    def read_kbdmap_choices(self):
        with open('/usr/share/X11/xkb/rules/xorg.lst', 'r') as f:
            key = None
            items = collections.defaultdict(list)
            for line in f.readlines():
                line = line.rstrip()
                if line.startswith('! '):
                    key = line[2:]
                if line.startswith('  '):
                    items[key].append(re.split(r'\s+', line.lstrip(), 1))

        choices = dict(items['layout'])
        for variant, desc in items['variant']:
            lang, title = desc.split(': ', 1)
            choices[f'{lang}.{variant}'] = title

        return dict(sorted(choices.items(), key=lambda t: t[1]))
