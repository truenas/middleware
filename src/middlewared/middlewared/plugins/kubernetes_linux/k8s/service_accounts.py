import asyncio
import errno
from base64 import b64decode

from middlewared.service import CallError


async def get_service_account_tokens_cas(api_client, service_account):
    details = []
    for secret in service_account.secrets:
        s_obj = (
            await api_client.list_secret_for_all_namespaces(field_selector=f'metadata.name={secret.name}')
        ).items[0]
        details.append({
            'secret_name': s_obj.metadata.name,
            'token': b64decode(s_obj.data['token']).decode(),
            'ca': s_obj.data.get('ca.crt'),
        })
    return details


async def get_service_account(api_client, service_account_name):
    accounts = await api_client.list_service_account_for_all_namespaces(
        field_selector=f'metadata.name={service_account_name}'
    )
    if not accounts.items:
        raise CallError(f'Unable to find "{service_account_name}" service account', errno=errno.ENOENT)
    else:
        return accounts.items[0]


async def get_service_account_details(api_client, svc_account):
    while True:
        try:
            svc_account = await get_service_account(api_client, svc_account)
        except Exception:
            await asyncio.sleep(5)
        else:
            break
    return (await get_service_account_tokens_cas(api_client, svc_account))[0]
