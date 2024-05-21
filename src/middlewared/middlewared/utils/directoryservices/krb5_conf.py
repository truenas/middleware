# This is a collection of utilities related to kerberos tickets
# and keytabs.
#
# Tests that do not require access to an actual KDC are provided
# in src/middlewared/middlewared/pytest/unit/utils/test_krb5.py
#
# Tests that require access to a KDC are provided as part of API
# test suite.

import logging
import os

from copy import deepcopy
from enum import auto, Enum
from tempfile import NamedTemporaryFile
from typing import Optional
from .krb5_constants import KRB_AppDefaults, KRB_ETYPE, KRB_LibDefaults, KRB_RealmProperty

logger = logging.getLogger(__name__)

KRB5_VALUE_BEGIN = '{'
KRB5_VALUE_END = '}'

APPDEFAULTS_SUPPORTED_OPTIONS = set(i.value[0] for i in KRB_AppDefaults)
LIBDEFAULTS_SUPPORTED_OPTIONS = set(i.value[0] for i in KRB_LibDefaults)
SUPPORTED_ETYPES = set(e.value for e in KRB_ETYPE)


class KRB5ConfSection(Enum):
    LIBDEFAULTS = auto()
    REALMS = auto()
    DOMAIN_REALM = auto()
    CAPATHS = auto()
    APPDEFAULTS = auto()
    PLUGINS = auto()


def validate_krb5_parameter(section, param, value):
    """
    Perform validation of krb5.conf parameters. If invalid parameters are written to
    the configuration file, then services that depend on kerberos will potentially
    break.
    """
    if isinstance(value, dict):
        for k, v in value.items():
            validate_krb5_parameter(section, k, v)

        return

    match section:
        # currently "auxiliary parameters" are only allowed in backend for
        # libdefaults and appdefaults sections of krb5.conf
        case KRB5ConfSection.APPDEFAULTS:
            section_enum = KRB_AppDefaults
        case KRB5ConfSection.LIBDEFAULTS:
            section_enum = KRB_LibDefaults
        case _:
            raise ValueError(f'{section}: unexpected section type')

    try:
        param_enum = section_enum[param.upper()]
    except KeyError:
        raise ValueError(
            f'{param}: unsupported option for [{section.name.lower()}] section'
        ) from None

    match param_enum.value[1]:
        case 'boolean':
            if value not in ('true', 'false'):
                raise ValueError(f'{value}: not a boolean value for parameter {param}')
        case 'string':
            if not isinstance(value, str):
                raise ValueError(f'{value}: not a string for parameter {param}')
        case 'etypes':
            if ',' in value:
                raise ValueError('enctypes should be space-delimited list')

            for enctype in value.split():
                if enctype.strip() not in SUPPORTED_ETYPES:
                    raise ValueError(f'{enctype}: unsupported enctype specified for parameter {param}')
        case 'time':
            if isinstance(value, str):
                if not value.isdigit():
                    # Technically krb5.conf allows multiple time formats
                    # but for simplicity we only allow seconds
                    raise ValueError(f'{value}: time must be expressed in seconds for parameter {param}')
            elif not isinstance(value, int):
                raise ValueError(f'{value}: time must be expressed in seconds for parameter {param}')
        case _:
            pass


def parse_krb_aux_params(
    section: KRB5ConfSection,
    section_conf: dict,
    aux_params: str
):
    """
    Parse auxiliary parameters and write them to the specified `section_conf`

    `section` - portion of krb5.conf file for which auxiliary parameters are being parsed

    `section_conf` - dictionary containing existing krb5 configuration, which will be
    updated with configuration specified in the `aux_params`

    `aux_params` - auxiliary parameters text blob to be parsed and used to update `section_conf`.
    """
    target = section_conf
    is_subsection = False

    # Parse auxiliary parameters for the specified section the krb5.conf file
    # is set up in the style of a Windows INI file. Sections are headed by
    # the section name, in square brackets. Each section may contain zero
    # or more relations of the form
    # `foo = bar`
    # or
    # ```
    # fubar = {
    #     foo = bar
    #     baz = quux
    # }
    # ```

    for line in aux_params.splitlines():
        if not line.strip():
            continue

        if len((entry := line.split('='))) < 1:
            # invalid line, keep legacy truenas behavior and silently skip
            continue

        param = entry[0].strip()

        if entry[-1].strip() == KRB5_VALUE_BEGIN:
            # `fubar = {` line, set `fubar` as target so that we properly
            # consolidate values if our defaults are overridden
            if is_subsection:
                raise ValueError('Invalid nesting of parameters')

            section_conf[param] = {}
            target = section_conf[param]
            is_subsection = True
            continue

        elif param == KRB5_VALUE_END:
            # `}` line ending previous
            target = section_conf
            is_subsection = False
            continue

        value = entry[1].strip()
        validate_krb5_parameter(section, param, value)
        target[param] = value


class KRB5Conf():
    def __init__(self):
        self.libdefaults = {}  # settings used by KRB5 library
        self.appdefaults = {}  # settings used by some KRB5 applications
        self.realms = {}  # realm-specific settings

    def __add_parameters(self, section: str, config: dict, auxiliary_parameters: Optional[list] = None):
        for param, value in config.items():
            validate_krb5_parameter(section, param, value)

        data = deepcopy(config)

        if auxiliary_parameters:
            parse_krb_aux_params(section, data, auxiliary_parameters)

        match section:
            case KRB5ConfSection.APPDEFAULTS:
                self.appdefaults = data
            case KRB5ConfSection.LIBDEFAULTS:
                self.libdefaults = data
            case _:
                raise ValueError(f'{section}: unexpected section type')

    def add_libdefaults(
        self,
        config: dict,
        auxiliary_parameters: Optional[list] = None
    ):
        """
        Add configuration for the [libdefaults] section of the krb5.conf file, replacing
        any existing configuration.

        Parameters may be specified in two ways (non-exclusive):

        `config` - a dictionary containing key-value pairs. Valid parameters are defined
        in krb5_constants.KRB_LibDefaults. These may be specified either as:

        `{"rdns": false}`

        to apply globally or

        `{"MYDOM.TEST": {"rdns": False}}` to apply only to a specific application.

        `auxiliary_parameters` - text field formatted per krb5.conf guidelines with parameters
        that are valid for the [appdefaults] section.

        ```
        MYDOM.TEST = {
            rdns = false
        }
        ```
        """
        self.__add_parameters(
            KRB5ConfSection.LIBDEFAULTS,
            config,
            auxiliary_parameters
        )

    def add_appdefaults(
        self,
        config: dict,
        auxiliary_parameters: Optional[str] = None
    ):
        """
        Add configuration for the [appdefaults] section of the krb5.conf file, replacing
        any existing configuration.

        Parameters may be specified in two ways (non-exclusive):

        `config` - a dictionary containing key-value pairs. Valid parameters are defined
        in krb5_constants.KRB_AppDefaults. These may be specified either as:

        `{"forwardable": True}`

        to apply globally or

        `{"pam": {"forwardable": True}}` to apply only to a specific application.

        `auxiliary_parameters` - text field formatted per krb5.conf guidelines with parameters
        that are valid for the [appdefaults] section.

        ```
        pam = {
            forwardable = true
        }
        ```
        """
        self.__add_parameters(
            KRB5ConfSection.APPDEFAULTS,
            config,
            auxiliary_parameters
        )

    def __parse_realm(self, realm_info: dict) -> dict:
        if 'realm' not in realm_info:
            raise ValueError('Realm information does not specify realm')

        for prop in (
            KRB_RealmProperty.ADMIN_SERVER.value[0],
            KRB_RealmProperty.KDC.value[0],
            KRB_RealmProperty.KPASSWD_SERVER.value[0]
        ):
            if prop in realm_info and not isinstance(realm_info[prop], list):
                raise ValueError(f'{prop}: property must be list')

        return {realm_info['realm']: {
            'realm': realm_info['realm'],
            'admin_server': realm_info[KRB_RealmProperty.ADMIN_SERVER.value[0]].copy(),
            'kdc': realm_info[KRB_RealmProperty.KDC.value[0]].copy(),
            'kpasswd_server': realm_info[KRB_RealmProperty.KPASSWD_SERVER.value[0]].copy(),
        }}

    def add_realms(self, realms: list) -> None:
        """
        Add configuration for [realms] section of krb5.conf file

        Realms are specified as a list of dictionaries containing the following keys

        `realm` - name of realm

        `admin_server` - list of hosts where administration server is running. Typically
        this is the primary kerberos server.

        `kdc` - list of kerberos domain controllers

        `kpasswd_server` list of servers where all password changes are performed

        NOTE: if admin_server, kdc, or kpasswd_server are unspecified, then they will be
        resolved through DNS.
        """
        clean_realms = {}
        for realm in realms:
            clean_realms.update(self.__parse_realm(realm))

        self.realms = clean_realms

    def __dump_a_parameter(self, parm: str, value):
        if isinstance(value, dict):
            out = f'\t{parm} = {KRB5_VALUE_BEGIN}\n'
            for k, v in value.items():
                if (val := self.__dump_a_parameter(k, v)) is None:
                    continue

                out += f'\t{val}'

            out += f'\t{KRB5_VALUE_END}\n'
            return out
        elif isinstance(value, list):
            if len(value) == 0:
                return None

            return f'\t{parm} = {" ".join(value)}\n'
        else:
            return f'\t{parm} = {value}\n'

    def __generate_libdefaults(self):
        kconf = "[libdefaults]\n"
        for parm, value in self.libdefaults.items():
            kconf += self.__dump_a_parameter(parm, value)

        return kconf + '\n'

    def __generate_appdefaults(self):
        kconf = "[appdefaults]\n"
        for parm, value in self.appdefaults.items():
            kconf += self.__dump_a_parameter(parm, value)

        return kconf + '\n'

    def __generate_realms(self):
        kconf = '[realms]\n'
        for realm in list(self.realms.keys()):
            this_realm = self.realms[realm].copy()
            this_realm.pop('realm')
            kconf += self.__dump_a_parameter(
                realm, {'default_domain': realm} | this_realm
            )

        return kconf + '\n'

    def __generate_domain_realms(self):
        kconf = '[domain_realms]\n'
        for realm in self.realms.keys():
            kconf += f'\t{realm.lower()} = {realm}\n'
            kconf += f'\t.{realm.lower()} = {realm}\n'
            kconf += f'\t{realm.upper()} = {realm}\n'
            kconf += f'\t.{realm.upper()} = {realm}\n'

        return kconf + '\n'

    def generate(self):
        """
        Generate krb5.conf file and return as string
        """
        kconf = self.__generate_libdefaults()
        kconf += self.__generate_appdefaults()
        kconf += self.__generate_realms()
        kconf += self.__generate_domain_realms()
        return kconf

    def write(self, path: Optional[str] = '/etc/krb5.conf'):
        """
        Write the stored krb5.conf file to the specified `path`
        """
        config = self.generate()
        with NamedTemporaryFile(delete=False) as f:
            f.write(config.encode())
            f.flush()

            os.rename(f.name, path)
