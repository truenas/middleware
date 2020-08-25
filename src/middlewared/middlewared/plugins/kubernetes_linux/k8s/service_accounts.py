from base64 import b64decode


async def get_service_account_tokens_cas(api_client, service_account):
    details = []
    for secret in service_account.secrets:
        s_obj = await api_client.list_secret_for_all_namespaces(field_selector=f'metadata.name={secret.name}').items[0]
        details.append({
            'secret_name': s_obj.metadata.name,
            'token': b64decode(s_obj.data['token']).decode(),
            'ca': s_obj.data.get('ca.crt'),
        })
    return details
