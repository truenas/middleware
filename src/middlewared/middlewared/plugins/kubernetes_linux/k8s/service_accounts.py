import asyncio
import errno

from middlewared.service import CallError


async def get_service_account_tokens_cas(api_client, service_account):
    token = await api_client.create_namespaced_service_account_token(
        name=service_account.metadata.name,
        namespace=service_account.metadata.namespace,
        body={'spec': {'expirationSeconds': 500000000}}
    )
    return token.status.token


async def get_service_account(api_client, service_account_name):
    accounts = await api_client.list_service_account_for_all_namespaces(
        field_selector=f'metadata.name={service_account_name}'
    )
    if not accounts.items or not accounts.items[0]:
        # We check if the item is not null because in some race conditions
        # the data we get from the api returns null which is of course not the service account we desire
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
    return await get_service_account_tokens_cas(api_client, svc_account)
