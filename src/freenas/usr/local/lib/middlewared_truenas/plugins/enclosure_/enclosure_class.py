import logging

from .element_types import ELEMENT_TYPES, ELEMENT_DESC
from .regex import RE


logger = logging.getLogger(__name__)


class Enclosure(object):

    def __init__(self, idx, stat, product):
        self.product = product
        self.stat = stat
        self.num = idx
        self.devname = f'ses{self.num}'
        self.encname = self.stat['name']
        self.encid = self.stat['id']
        self.model, self.controller = self._set_model_and_controller()
        self.status = ','.join(self.stat['status'])
        self.elements = self._parse_elements(self.stat['elements'])

    def _set_model_and_controller(self):
        model = ''
        controller = False
        # enclosure head-unit detection
        if RE.M.value.match(self.encname):
            model = 'M Series'
            controller = True
        elif RE.X.value.match(self.encname):
            model = 'X Series'
            controller = True
        elif self.encname.startswith('ECStream 3U16+4R-4X6G.3'):
            cooling_elements = [v for k, v in self.stat['elements'].items() if v['type'] == 3]
            if any(i['descriptor'] == 'SD_9GV12P1J_12R6K4' for i in cooling_elements):
                # z series head-unit uses same enclosure as E16
                # the distinguishing identifier being a cooling element
                model = 'Z Series'
                controller = True
            else:
                model = 'E16'
        elif RE.R.value.match(self.encname) or RE.R20.value.match(self.encname) or RE.R50.value.match(self.encname):
            model = self.product.replace('TRUENAS-', '')
            controller = True
        elif self.encname == 'AHCI SGPIO Enclosure 2.00':
            if self.product in RE.R20_VARIANTS.value:
                model = self.product.replace('TRUENAS-', '')
                controller = True
            elif RE.MINI.value.match(self.product):
                # TrueNAS Mini's do not have their product name stripped
                model = self.product
                controller = True
        # enclosure shelf detection
        elif self.encname.startswith('ECStream 3U16RJ-AC.r3'):
            model = 'E16'
        elif self.encname.startswith('Storage 1729'):
            model = 'E24'
        elif self.encname.startswith('QUANTA JB9 SIM'):
            model = 'E60'
        elif self.encname.startswith('CELESTIC X2012'):
            model = 'ES12'
        elif RE.ES24.value.match(self.encname):
            model = 'ES24'
        elif RE.ES24F.value.match(self.encname):
            model = 'ES24F'
        elif self.encname.startswith('CELESTIC R0904'):
            model = 'ES60'
        elif self.encname.startswith('HGST H4102-J'):
            model = 'ES102'

        return model, controller

    def _parse_elements(self, elements):
        final = {}
        for slot, element in elements.items():
            try:
                element_type = ELEMENT_TYPES[element['type']]
            except KeyError:
                # means the element type that's being
                # reported to us is unknown so log it
                # and continue on
                logger.warning('Unknown element type: %r for %r', element['type'], self.devname)
                continue

            try:
                element_status = ELEMENT_DESC[element['status'][0]]
            except KeyError:
                # means the elements status reported by the enclosure
                # is not mapped so just report unknown
                element_status = 'UNKNOWN'

            if element_type[0] not in final:
                # first time seeing this element type so add it
                final[element_type[0]] = {}

            if self.model == 'Z Series' and slot > 16:
                # zseries head-unit reports 20 disk slots but only
                # 16 are available to the end-user so ignore the
                # other 4 slots
                continue

            # convert list of integers representing the elements
            # raw status to an integer so it can be converted
            # appropriately based on the element type
            value_raw = 0
            for val in element['status']:
                value_raw = (value_raw << 8) + val

            parsed = {slot: {
                'descriptor': element['descriptor'],
                'status': element_status,
                'value': element_type[1](value_raw),
                'value_raw': value_raw,
            }}
            if element_type[0] == 'Array Device Slot':
                # we always have a 'dev' key that's been strip()'ed,
                # we just need to pull out the da# (if there is one)
                da = [y for y in element['dev'].split(',') if not y.startswith('pass')]
                if da:
                    parsed[slot].update({'dev': da[0]})
                else:
                    parsed[slot].update({'dev': ''})

            final[element_type[0]].update(parsed)

        return final
