from middlewared.utils.metrics.arcstat import ArcStatDescriptions, get_arc_stats

from bases.FrameworkServices.SimpleService import SimpleService


CHARTS = {
    'free': {
        'options': [None, 'free', 'Bytes', 'free', ArcStatDescriptions['free'], 'line'],
        'lines': [
            ['free', 'free', 'absolute'],
        ]
    },
    'avail': {
        'options': [None, 'avail', 'Bytes', 'avail', ArcStatDescriptions['avail'], 'line'],
        'lines': [
            ['avail', 'avail', 'absolute'],
        ]
    },
    'size': {
        'options': [None, 'size', 'Bytes', 'size', ArcStatDescriptions['size'], 'line'],
        'lines': [
            ['size', 'size', 'absolute'],
        ]
    },
    'dread': {
        'options': [None, 'dread', 'dread/s', 'dread', ArcStatDescriptions['dread'], 'line'],
        'lines': [
            ['dread', 'dread', 'incremental'],
        ]
    },
    'ddread': {
        'options': [None, 'ddread', 'ddread/s', 'ddread', ArcStatDescriptions['ddread'], 'line'],
        'lines': [
            ['ddread', 'ddread', 'incremental'],
        ]
    },
    'dmread': {
        'options': [None, 'dmread', 'dmread/s', 'dmread', ArcStatDescriptions['dmread'], 'line'],
        'lines': [
            ['dmread', 'dmread', 'incremental'],
        ]
    },
    'ddhit': {
        'options': [None, 'ddhit', 'ddhit/s', 'ddhit', ArcStatDescriptions['ddhit'], 'line'],
        'lines': [
            ['ddhit', 'ddhit', 'incremental'],
        ]
    },
    'ddioh': {
        'options': [None, 'ddioh', 'ddioh/s', 'ddioh', ArcStatDescriptions['ddioh'], 'line'],
        'lines': [
            ['ddioh', 'ddioh', 'incremental'],
        ]
    },
    'ddmis': {
        'options': [None, 'ddmis', 'ddmis/s', 'ddmis', ArcStatDescriptions['ddmis'], 'line'],
        'lines': [
            ['ddmis', 'ddmis', 'incremental'],
        ]
    },
    'ddh_p': {
        'options': [None, 'ddh', 'ddh%', 'ddh', ArcStatDescriptions['ddh%'], 'line'],
        'lines': [
            ['ddh_p', 'ddh', 'percentage-of-incremental-row'],
        ]
    },
    'ddi_p': {
        'options': [None, 'ddi', 'ddi%', 'ddi', ArcStatDescriptions['ddi%'], 'line'],
        'lines': [
            ['ddi_p', 'ddi', 'percentage-of-incremental-row'],
        ]
    },
    'ddm_p': {
        'options': [None, 'ddm', 'ddm%', 'ddm', ArcStatDescriptions['ddm%'], 'line'],
        'lines': [
            ['ddm_p', 'ddm', 'percentage-of-incremental-row'],
        ]
    },
    'dmhit': {
        'options': [None, 'dmhit', 'dmhit', 'dmhit', ArcStatDescriptions['dmhit'], 'line'],
        'lines': [
            ['dmhit', 'dmhit', 'incremental'],
        ]
    },
    'dmioh': {
        'options': [None, 'dmioh', 'dmioh', 'dmioh', ArcStatDescriptions['dmioh'], 'line'],
        'lines': [
            ['dmioh', 'dmioh', 'incremental'],
        ]
    },
    'dmmis': {
        'options': [None, 'dmmis', 'dmmis', 'dmmis', ArcStatDescriptions['dmmis'], 'line'],
        'lines': [
            ['dmmis', 'dmmis', 'incremental'],
        ]
    },
    'dmh_p': {
        'options': [None, 'dmh', 'dmh%', 'dmh', ArcStatDescriptions['dmh%'], 'line'],
        'lines': [
            ['dmh_p', 'dmh', 'percentage-of-incremental-row'],
        ]
    },
    'dmi_p': {
        'options': [None, 'dmi', 'dmi%', 'dmi', ArcStatDescriptions['dmi%'], 'line'],
        'lines': [
            ['dmi_p', 'dmi', 'percentage-of-incremental-row'],
        ]
    },
    'dmm_p': {
        'options': [None, 'dmm', 'dmm%', 'dmm', ArcStatDescriptions['dmm%'], 'line'],
        'lines': [
            ['dmm_p', 'dmm', 'percentage-of-incremental-row'],
        ]
    },
    'l2hits': {
        'options': [None, 'l2hits', 'l2hits', 'l2hits', ArcStatDescriptions['l2hits'], 'line'],
        'lines': [
            ['l2hits', 'l2hits', 'incremental'],
        ]
    },
    'l2miss': {
        'options': [None, 'l2miss', 'l2miss', 'l2miss', ArcStatDescriptions['l2miss'], 'line'],
        'lines': [
            ['l2miss', 'l2miss', 'incremental'],
        ]
    },
    'l2read': {
        'options': [None, 'l2read', 'l2read', 'l2read', ArcStatDescriptions['l2read'], 'line'],
        'lines': [
            ['l2read', 'l2read', 'incremental'],
        ]
    },
    'l2hit_p': {
        'options': [None, 'l2hit', 'l2hit%', 'l2hit', ArcStatDescriptions['l2hit%'], 'line'],
        'lines': [
            ['l2hit_p', 'l2hit', 'percentage-of-incremental-row'],
        ]
    },
    'l2miss_p': {
        'options': [None, 'l2miss', 'l2miss%', 'l2miss', ArcStatDescriptions['l2miss%'], 'line'],
        'lines': [
            ['l2miss_p', 'l2miss', 'percentage-of-incremental-row'],
        ]
    },
    'l2bytes': {
        'options': [None, 'l2bytes', 'l2bytes', 'l2bytes', ArcStatDescriptions['l2bytes'], 'line'],
        'lines': [
            ['l2bytes', 'l2bytes', 'incremental'],
        ]
    },
    'l2wbytes': {
        'options': [None, 'l2wbytes', 'l2wbytes', 'l2wbytes', ArcStatDescriptions['l2wbytes'], 'line'],
        'lines': [
            ['l2wbytes', 'l2wbytes', 'incremental'],
        ]
    },
}


class Service(SimpleService):
    def __init__(self, configuration=None, name=None):
        SimpleService.__init__(self, configuration=configuration, name=name)
        self.order = [chart_name.replace('%', '_p') for chart_name in ArcStatDescriptions.keys()]
        self.definitions = CHARTS

    def get_data(self):
        data = {}
        for key, value in get_arc_stats().items():
            data[key.replace('%', '_p')] = value[0]
        return data

    def check(self):
        return True
