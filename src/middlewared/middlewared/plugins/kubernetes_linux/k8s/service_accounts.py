from base64 import b64decode


async def get_service_account_tokens(client, service_account):
    return [
        {
            'secret_name': secret.name,
            'token': b64decode(client.list_secret_for_all_namespaces(
                field_selector=f'metadata.name={secret.name}'
            ).items[0].data['token'])
        } for secret in service_account.secrets
    ]
