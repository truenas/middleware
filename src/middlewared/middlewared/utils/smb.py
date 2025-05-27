import enum
from unicodedata import category


class SMBUnixCharset(enum.StrEnum):
    UTF_8 = 'UTF-8'
    GB2312 = 'GB2312'
    HZ_GB_2312 = 'HZ-GB-2312'
    CP1361 = 'CP1361'
    BIG5 = 'BIG5'
    BIG5HKSCS = 'BIG5HKSCS'
    CP037 = 'CP037'
    CP273 = 'CP273'
    CP424 = 'CP424'
    CP437 = 'CP437'
    CP500 = 'CP500'
    CP775 = 'CP775'
    CP850 = 'CP850'
    CP852 = 'CP852'
    CP855 = 'CP855'
    CP857 = 'CP857'
    CP858 = 'CP858'
    CP860 = 'CP860'
    CP861 = 'CP861'
    CP862 = 'CP862'
    CP863 = 'CP863'
    CP864 = 'CP864'
    CP865 = 'CP865'
    CP866 = 'CP866'
    CP869 = 'CP869'
    CP932 = 'CP932'
    CP949 = 'CP949'
    CP950 = 'CP950'
    CP1026 = 'CP1026'
    CP1125 = 'CP1125'
    CP1140 = 'CP1140'
    CP1250 = 'CP1250'
    CP1251 = 'CP1251'
    CP1252 = 'CP1252'
    CP1253 = 'CP1253'
    CP1254 = 'CP1254'
    CP1255 = 'CP1255'
    CP1256 = 'CP1256'
    CP1257 = 'CP1257'
    CP1258 = 'CP1258'
    EUC_JIS_2004 = 'EUC_JIS_2004'
    EUC_JISX0213 = 'EUC_JISX0213'
    EUC_JP = 'EUC_JP'
    EUC_KR = 'EUC_KR'
    GB18030 = 'GB18030'
    GBK = 'GBK'
    HZ = 'HZ'
    ISO2022_JP = 'ISO2022_JP'
    ISO2022_JP_1 = 'ISO2022_JP_1'
    ISO2022_JP_2 = 'ISO2022_JP_2'
    ISO2022_JP_2004 = 'ISO2022_JP_2004',
    ISO2022_JP_3 = 'ISO2022_JP_3'
    ISO2022_JP_EXT = 'ISO2022_JP_EXT'
    ISO2022_KR = 'ISO2022_KR'
    ISO8859_1 = 'ISO8859_1'
    ISO8859_2 = 'ISO8859_2'
    ISO8859_3 = 'ISO8859_3'
    ISO8859_4 = 'ISO8859_4'
    ISO8859_5 = 'ISO8859_5'
    ISO8859_6 = 'ISO8859_6'
    ISO8859_7 = 'ISO8859_7'
    ISO8859_8 = 'ISO8859_8'
    ISO8859_9 = 'ISO8859_9'
    ISO8859_10 = 'ISO8859_10'
    ISO8859_11 = 'ISO8859_11'
    ISO8859_13 = 'ISO8859_13'
    ISO8859_14 = 'ISO8859_14'
    ISO8859_15 = 'ISO8859_15'
    ISO8859_16 = 'ISO8859_16'
    JOHAB = 'JOHAB'
    KOI8_R = 'KOI8_R'
    KZ1048 = 'KZ1048'
    LATIN_1 = 'LATIN_1'
    MAC_CYRILLIC = 'MAC_CYRILLIC'
    MAC_GREEK = 'MAC_GREEK'
    MAC_ICELAND = 'MAC_ICELAND'
    MAC_LATIN2 = 'MAC_LATIN2'
    MAC_ROMAN = 'MAC_ROMAN'
    MAC_TURKISH = 'MAC_TURKISH'
    PTCP154 = 'PTCP154'
    SHIFT_JIS = 'SHIFT_JIS'
    SHIFT_JIS_2004 = 'SHIFT_JIS_2004'
    SHIFT_JISX0213 = 'SHIFT_JISX0213'
    TIS_620 = 'TIS_620'
    UTF_16 = 'UTF_16'
    UTF_16_BE = 'UTF_16_BE'
    UTF_16_LE = 'UTF_16_LE'


class SMBSharePurpose(enum.StrEnum):
    DEFAULT_SHARE = 'DEFAULT_SHARE'
    LEGACY_SHARE = 'LEGACY_SHARE'
    TIMEMACHINE_SHARE = 'TIMEMACHINE_SHARE'
    MULTIPROTOCOL_SHARE = 'MULTIPROTOCOL_SHARE'
    PRIVATE_DATASETS_SHARE = 'PRIVATE_DATASETS_SHARE'
    EXTERNAL_SHARE = 'EXTERNAL_SHARE'
    TIME_LOCKED_SHARE = 'TIME_LOCKED_SHARE'


INVALID_SHARE_NAME_CHARACTERS = frozenset({
    '%', '<', '>', '*', '?', '|', '/', '\\', '+', '=', ';', ':', '"', ',', '[', ']'
})
RESERVED_SHARE_NAMES = frozenset({'global', 'printers', 'homes', 'admin$', 'ipc$'})
SUPPORTED_SMB_VARIABLES = frozenset({'U', 'u', 'G'})  # see man 5 smb.conf "VARIABLE SUBSTITUTIONS"


def validate_smb_share_name(name: str) -> str:
    # Standards for SMB share name are defined in MS-FSCC 2.1.6
    # We are slighly more strict in that blacklist all unicode control characters

    if not isinstance(name, str):
        raise ValueError(f'{name}: not a string')

    if not len(name):
        raise ValueError('Share name must contain at least one character')

    if len(name) > 80:
        raise ValueError(f'{name}: share name must not exceed 80 characters in length')

    if name.lower() in RESERVED_SHARE_NAMES:
        raise ValueError(f'{name}: share name is reserved.')

    if invalid_characters := (INVALID_SHARE_NAME_CHARACTERS & set(name)):
        raise ValueError(f'{name}: share name contains the following invalid characters: {", ".join(invalid_characters)}')

    if any(category(char) == 'Cc' for char in name):
        raise ValueError(f'{name}: share name contains unicode control characters')

    return name


def validate_smb_path_suffix(suffix: str) -> str:
    if not suffix:
        raise ValueError('Invalid path schema')

    components = suffix.split('/')
    if len(components) > 2:
        raise ValueError('Naming schema may not contain more than two components.')

    for component in components:
        if '%' not in component:
            continue

        if component.split('%')[1][:1] not in SUPPORTED_SMB_VARIABLES:
            raise ValueError(f'{component}: not a supported naming schema component')

    return suffix
