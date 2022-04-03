import copy

from middlewared.schema import Bool, Datetime, Dict, Int, List, OROperator, Str


CERT_ENTRY = Dict(
    'certificate_entry',
    Int('id'),
    Int('type'),
    Str('name'),
    Str('certificate', null=True, max_length=None),
    Str('privatekey', null=True, max_length=None),
    Str('CSR', null=True, max_length=None),
    Str('acme_uri', null=True),
    Dict('domains_authenticators', additional_attrs=True, null=True),
    Int('renew_days'),
    Datetime('revoked_date', null=True),
    Dict('signedby', additional_attrs=True, null=True),
    Str('root_path'),
    Dict('acme', additional_attrs=True, null=True),
    Str('certificate_path', null=True),
    Str('privatekey_path', null=True),
    Str('csr_path', null=True),
    Str('cert_type'),
    Bool('revoked'),
    OROperator(Str('issuer', null=True), Dict('issuer', additional_attrs=True, null=True), name='issuer'),
    List('chain_list', items=[Str('certificate', max_length=None)]),
    Str('country', null=True),
    Str('state', null=True),
    Str('city', null=True),
    Str('organization', null=True),
    Str('organizational_unit', null=True),
    List('san', items=[Str('san_entry')], null=True),
    Str('email', null=True),
    Str('DN', null=True),
    Str('subject_name_hash', null=True),
    Str('digest_algorithm', null=True),
    Str('from', null=True),
    Str('common', null=True, max_length=None),
    Str('until', null=True),
    Str('fingerprint', null=True),
    Str('key_type', null=True),
    Str('internal', null=True),
    Int('lifetime', null=True),
    Int('serial', null=True),
    Int('key_length', null=True),
    Bool('chain', null=True),
    Bool('CA_type_existing'),
    Bool('CA_type_internal'),
    Bool('CA_type_intermediate'),
    Bool('cert_type_existing'),
    Bool('cert_type_internal'),
    Bool('cert_type_CSR'),
    Bool('parsed'),
    Bool('can_be_revoked'),
    Dict('extensions', additional_attrs=True),
    List('revoked_certs'),
    Str('crl_path'),
    Int('signed_certificates'),
)


def get_ca_result_entry():
    entry = copy.deepcopy(CERT_ENTRY)
    entry.name = 'certificateauthority_entry'
    entry.attrs['add_to_trusted_store'] = Bool('add_to_trusted_store')
    return entry
