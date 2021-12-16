import re
import sysctl

from middlewared.service import Service

MCA = re.compile(r'.*MCA:.*(COR|UNCOR).*')
APEI = re.compile(r'.*APEI.*(Recoverable|Fatal|Corrected|Informational).*')


class HardwareService(Service):

    class Config:
        private = True

    def report(self):
        if self.middleware.call_sync('system.is_enterprise'):
            return self._parse_msgbuf()
        return {'MCA_EVENTS': [], 'APEI_EVENTS': []}

    def _parse_msgbuf(self, msgbuf=None):
        """
        Parse `kern.msgbuf` sysctl for any MCA or APEI events.
        `msgbug` List of strings from kern.msgbuf sysctl output
        """
        if msgbuf is None:
            # using a kwarg to simplify unit tests
            msgbuf = sysctl.filter('kern.msgbuf')[0].value.split('\n')

        # we always append a bogus line at the end to ensure
        # the parsing of the log file works as intended. This
        # is to insulate us from an edge-case where the log
        # only has, literally, a single APEI event. In this
        # edge-case, without the ending bogus line, `apei_dict`
        # will never get appended to the events['APEI_EVENTS'] key.
        msgbuf.append('BOGUS LINE\n')

        apei_event = None
        apei_dict = dict()
        events = {'MCA_EVENTS': [], 'APEI_EVENTS': []}
        for line in msgbuf:
            if line:
                if (mca_match := MCA.match(line)):
                    mca_event = mca_match.group().strip()
                    if mca_event not in events['MCA_EVENTS']:
                        events['MCA_EVENTS'].append(mca_event)
                elif (apei_match := APEI.match(line)):
                    # Line looks like this:
                    # 'APEI Corrected Memory Error:'
                    # Which means this is the first line starting a series
                    # of APEI messages (the next (up to) 25 lines could be related)
                    apei_event = apei_match.group().strip()
                elif apei_event:
                    # Lines look like this: (notice single-space indent)
                    # ' Error Status: 0x0'
                    # ' Physical Address: 0x72aed744c0'
                    # ' Physical Address Mask: 0x3fffffffffc0'
                    if line[0].isspace() and ':' in line:
                        key, value = line.split(':', 1)
                        if not key:
                            continue

                        if apei_event not in apei_dict:
                            apei_dict[apei_event] = {}
                        apei_dict[apei_event][key.strip()] = value.strip()
                    elif apei_dict:
                        events['APEI_EVENTS'].append(apei_dict)
                        apei_dict = dict()
                        apei_event = None
        return events
