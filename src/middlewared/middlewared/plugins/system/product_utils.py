from datetime import date

from licenselib.license import ContractType, Features, License

from middlewared.utils.license import LICENSE_ADDHW_MAPPING


LICENSE_FILE = '/data/license'


def get_license(include_raw_license: bool = False) -> dict | None:
    try:
        with open(LICENSE_FILE) as f:
            raw_license = f.read().strip('\n')
            licenseobj = License.load(raw_license)
    except Exception:
        return

    license_ = {
        'model': licenseobj.model,
        'system_serial': licenseobj.system_serial,
        'system_serial_ha': licenseobj.system_serial_ha,
        'contract_type': ContractType(licenseobj.contract_type).name.upper(),
        'contract_start': licenseobj.contract_start,
        'contract_end': licenseobj.contract_end,
        'legacy_contract_hardware': (
            licenseobj.contract_hardware.name.upper()
            if licenseobj.contract_type == ContractType.legacy
            else None
        ),
        'legacy_contract_software': (
            licenseobj.contract_software.name.upper()
            if licenseobj.contract_type == ContractType.legacy
            else None
        ),
        'customer_name': licenseobj.customer_name,
        'expired': licenseobj.expired,
        'features': [i.name.upper() for i in licenseobj.features],
        'addhw': licenseobj.addhw,
        'addhw_detail': [],
    }

    for quantity, code in licenseobj.addhw:
        try:
            license_['addhw_detail'].append(f'{quantity} x {LICENSE_ADDHW_MAPPING[code]} Expansion shelf')
        except KeyError:
            license_['addhw_detail'].append(f'<Unknown hardware {code}>')

    if Features.fibrechannel not in licenseobj.features and licenseobj.contract_start < date(2017, 4, 14):
        # Licenses issued before 2017-04-14 had a bug in the feature bit for fibrechannel, which
        # means they were issued having dedup+jails instead.
        if Features.dedup in licenseobj.features and Features.jails in licenseobj.features:
            license_['features'].append(Features.fibrechannel.name.upper())

    if include_raw_license:
        license_['raw_license'] = raw_license

    return license_
