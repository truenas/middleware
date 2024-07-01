import asyncio
from logging import getLogger

from middlewared.plugins.enclosure_.enums import JbofModels
from middlewared.plugins.enclosure_.jbof.es24n import (is_this_an_es24n,
                                                       map_es24n)
from middlewared.plugins.jbof.redfish import (AsyncRedfishClient,
                                              InvalidCredentialsError)

LOGGER = getLogger(__name__)


JBOF_MODEL_ATTR = 'model'
JBOF_URI_ATTR = 'uri'


async def get_redfish_clients(jbofs):
    clients = dict()
    for jbof in jbofs:
        try:
            rclient = await AsyncRedfishClient.cache_get(jbof['uuid'], jbofs)
            clients[jbof['uuid']] = rclient
        except InvalidCredentialsError:
            LOGGER.error('Failed to login to redfish ip %r %r', jbof['mgmt_ip1'], jbof['mgmt_ip2'])
        except Exception:
            LOGGER.error('Unexpected failure creating redfish client object', exc_info=True)

    return clients


async def get_enclosure_model(rclient):
    model = uri = None
    try:
        chassis = await rclient.chassis()
    except Exception:
        LOGGER.error('Unexpected failure enumerating chassis info', exc_info=True)
        return model, uri

    model, uri = await is_this_an_es24n(rclient)
    if all((model, uri)):
        return model, uri

    try:
        for _, uri in chassis.items():
            info = await rclient.get(uri)
            if info.ok:
                try:
                    model = JbofModels(info.json().get('Model', '')).name
                    return model, uri
                except ValueError:
                    # Using parenthesis on the enum checks the string BY VALUE
                    # and NOT BY NAME. If you were to use square brackets [],
                    # then a KeyError will be raised.
                    continue
    except Exception:
        LOGGER.error('Unexpected failure determing enclosure model', exc_info=True)

    return model, uri


async def map_jbof(jbof_query):
    result = list()
    futures = []
    for rclient in (await get_redfish_clients(jbof_query)).values():
        # Since we're *already* keeping a client object around, cache a couple
        # of attributes to make things faster after the first time.
        model = rclient.get_attribute(JBOF_MODEL_ATTR)
        uri = rclient.get_attribute(JBOF_URI_ATTR)
        if not model or not uri:
            model, uri = await get_enclosure_model(rclient)
            rclient.set_attribute(JBOF_MODEL_ATTR, model)
            rclient.set_attribute(JBOF_URI_ATTR, uri)

        if model == JbofModels.ES24N.name:
            futures.append(map_es24n(model, rclient, uri))

    # Now fetch the data from each JBOF in parallel
    for ans in await asyncio.gather(*futures, return_exceptions=True):
        if ans and not isinstance(ans, Exception):
            result.extend(ans)

    return result


async def set_slot_status(ident, slot, status):
    # For the time being we're assume that all models are using the same
    # redfish mechanism.  If this changes add a model parameter to the
    # function so that we can dispatch here as required.
    rclient = await AsyncRedfishClient.cache_get(ident)
    uri = rclient.get_attribute(JBOF_URI_ATTR)
    if not uri:
        _, uri = await get_enclosure_model(rclient)
    fulluri = f'{uri}/Drives/{slot}'

    match status:
        case 'CLEAR':
            await rclient.post(fulluri, data={'LocationIndicatorActive': False})
        case 'IDENT':
            await rclient.post(fulluri, data={'LocationIndicatorActive': True})
        case _:
            raise ValueError('Unsupported slot status', status)
