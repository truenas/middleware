CERT_RENEW_DAYS = 5
CLAIM_TOKEN_CACHE_KEY = 'truenas_connect_claim_token'


def get_account_id_and_system_id(config: dict) -> dict | None:
    jwt_details = config['registration_details'] or {}
    if all(jwt_details.get(k) for k in ('account_id', 'system_id')) is False:
        return None

    return {
        'account_id': jwt_details['account_id'],
        'system_id': jwt_details['system_id'],
    }
