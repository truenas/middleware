import re
import subprocess
from xml.etree import ElementTree as ET

import sysctl
from middlewared.schema import Dict, Int, Str, accepts
from middlewared.service import CRUDService, filterable, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils import filter_list


class FCPortModel(sa.Model):
    __tablename__ = 'services_fibrechanneltotarget'

    id = sa.Column(sa.Integer(), primary_key=True)
    fc_port = sa.Column(sa.String(10))
    fc_target_id = sa.Column(sa.ForeignKey('services_iscsitarget.id'), nullable=True, index=True)


class FCPortService(CRUDService):

    @filterable
    def query(self, filters, options):
        status = {'local': '', 'remote': ''}
        if self.middleware.call_sync("failover.licensed"):
            if self.middleware.call_sync("failover.status") == 'MASTER':
                status['local'] = ' (Active Controller)'
                status['remote'] = ' (Standby Controller)'
            else:
                status['local'] = ' (Standby Controller)'
                status['remote'] = ' (Active Controller)'

        fcportmap = {}
        for fbtt in self.middleware.call_sync("datastore.query", "services.fibrechanneltotarget"):
            fcportmap[fbtt["fc_port"]] = fbtt["fc_target"]

        results = []
        xml = subprocess.check_output(["ctladm", "portlist", "-x"], encoding="utf-8")
        for e in ET.fromstring(xml).findall(".//*[frontend_type='camtgt']"):
            name = e.find("./port_name").text
            reg = re.search(r"\d+", name)
            if reg:
                port = reg.group(0)
            else:
                port = "0"
            vport = e.find("./physical_port").text
            if vport != "0":
                name += f"/{vport}"
            state = "NO_LINK"
            speed = None
            wwpn = None
            if vport == "0":
                mibname = port
            else:
                mibname = f"{port}.chan{vport}"
            mib = f"dev.isp.{mibname}.loopstate"
            loopstate = sysctl.filter(mib)
            if loopstate:
                loopstate = loopstate[0].value
                if loopstate > 0 and loopstate < 10:
                    state = "SCANNING"
                elif loopstate == 10:
                    state = "READY"
                if loopstate > 0:
                    speedres = sysctl.filter(f"dev.isp.{mibname}.speed")
                    if speedres:
                        speed = speedres[0].value
            mib = f"dev.isp.{mibname}.wwpn"
            _filter = sysctl.filter(mib)
            if _filter:
                wwpn = f"naa.{_filter[0].value:x}"
            if name in fcportmap:
                targetobj = fcportmap[name]
                if targetobj is not None:
                    mode = "TARGET"
                    target = fcportmap[name]["id"]
                else:
                    mode = "INITIATOR"
                    target = None
            else:
                mode = "DISABLED"
                target = None

            # we're in the camtgt loop which means the initiators
            # here represent the local ports of this controller
            initiators = []
            for i in e.findall("./initiator"):
                initiators.append(i.text + status['local'])

            if status['local']:
                # loop over other controller ports
                for j in ET.fromstring(xml).findall(".//*[frontend_type='ha']"):
                    port_name = j.find("./port_name").text
                    if ":" in port_name:
                        port_name = port_name.split(":", 1)[1]
                    physical_port = j.find("./physical_port").text
                    if physical_port != "0":
                        port_name += f"/{physical_port}"
                    if port_name != name:
                        continue
                    for i in j.findall("./initiator"):
                        initiators.append(i.text + status['remote'])

            results.append(dict(
                id=name,
                port=port,
                vport=vport,
                name=name,
                wwpn=wwpn,
                mode=mode,
                target=target,
                state=state,
                speed=speed,
                initiators=initiators,
            ))

        return filter_list(results, filters=filters or [], options=options or {})

    @accepts(
        Str("id"),
        Dict(
            "fcport_update",
            Str("mode", enum=["INITIATOR", "TARGET", "DISABLED"], required=True),
            Int("target", null=True, default=None),
        ),
    )
    def do_update(self, id, data):
        verrors = ValidationErrors()

        if data["mode"] == "TARGET":
            if data["target"] is None:
                verrors.add("fcport_update.target", "This field is required when mode is TARGET")
            else:
                try:
                    self.middleware.call_sync("iscsi.target.query", [["id", "=", data["target"]]], {"get": True})
                except IndexError:
                    verrors.add("fcport_update.target", "This target does not exist")

        if verrors:
            raise verrors

        self.middleware.call_sync("datastore.delete", "services.fibrechanneltotarget", [["fc_port", "=", id]])

        port = id.replace("isp", "").replace("/", ",")
        if "," in port:
            port_number, vport = port.split(",", 1)
            mibname = f"{port_number}.chan{vport}"
        else:
            mibname = port

        role = sysctl.filter(f"dev.isp.{mibname}.role")
        if role:
            role = role[0]
        tun_var = f"hint.isp.{mibname}.role"

        set_sysctl = {}
        reload_loader = False

        if data["mode"] == "INITATOR":
            if role:
                # From disabled to initiator, just set sysctl
                if role.value == 0:
                    role.value = 2
                # From target to initiator, reload ctld then set to 2
                elif role.value == 1:
                    set_sysctl[mibname] = 2

            try:
                tun = self.middleware.call_sync("tunable.query", [["var", "=", tun_var]], {"get": True})
            except IndexError:
                self.middleware.call_sync("tunable.insert", {
                    "var": tun_var,
                    "value": "2",
                    "type": "LOADER",
                })
                reload_loader = True
            else:
                if tun["value"] != "2":
                    self.middleware.call_sync("tunable.update", tun["id"], {
                        "value": "2",
                    })
                    reload_loader = True

        if data["mode"] == "DISABLED":
            if role:
                # From initiator to disabled, just set sysctl
                if role.value == 2:
                    role.value = 0

            try:
                tun = self.middleware.call_sync("tunable.query", [["var", "=", tun_var]], {"get": True})
            except IndexError:
                pass
            else:
                self.middleware.call_sync("tunable.delete", tun["id"])
                reload_loader = True

        if data["mode"] == "TARGET":
            if role:
                # From initiator to target, first set sysctl
                if role.value == 2:
                    role.value = 0

            try:
                tun = self.middleware.call_sync("tunable.query", [["var", "=", tun_var]], {"get": True})
            except IndexError:
                pass
            else:
                self.middleware.call_sync("tunable.delete", tun["id"])
                reload_loader = True

        if data["mode"] != "DISABLED":
            self.middleware.call_sync("datastore.insert", "services.fibrechanneltotarget", {
                "fc_port": id,
                "fc_target": data["target"],
            })

        self.middleware.call_sync("service.reload", "iscsitarget")

        for mibname, val in set_sysctl.items():
            role = sysctl.filter(f"dev.isp.{mibname}.role")
            if role:
                role = role[0]
                role.value = val

        if reload_loader:
            self.middleware.call_sync("service.reload", "loader")

        return self.middleware.run_coroutine(self._get_instance(id))
