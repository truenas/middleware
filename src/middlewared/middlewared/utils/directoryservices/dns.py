import os

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from json import JSONDecodeError
from threading import Lock
from middlewared.utils.io import write_if_changed
from middlewared.utils.time_utils import utc_now
from truenas_api_client import ejson as json
from .constants import DS_HA_STATE_DIR


DS_DNS_STATE_FILE = os.path.join(DS_HA_STATE_DIR, '.nsupdate_state.json')
# When DNS scavenging is enabled in AD, the default refresh interval in AD DNS is 7 days.
# Then after an additional 7 days by default (the 14 day mark) the DC will remove the record.
DEFAULT_RECORD_EXPIRY = timedelta(days=7)
NSUPDATE_LOCK = Lock()
NSUPDATE_STATE_VERSION = 1


@dataclass()
class NSUpdateState:
    fqdn: str
    expiry: datetime
    version: int


def __get_nsupdate_state(fqdn: str) -> NSUpdateState | None:
    try:
        with open(DS_DNS_STATE_FILE, 'r') as f:
            data = NSUpdateState(**json.loads(f.read()))
    except FileNotFoundError:
        # File doesn't exist, ergo no state
        return None
    except JSONDecodeError:
        # File for some reason has invalid JSON. Nothing we can do about this other than treat as having no state.
        return None
    except TypeError:
        # Contents of file does not match the expected schema. This most likely means we updated and the schema changed.
        # It should be safe to discard the info and require a renewal
        return None

    # Make sure data version and types are correct.
    if data.version != NSUPDATE_STATE_VERSION:
        return None

    elif not isinstance(data.fqdn, str):
        return None

    elif not isinstance(data.expiry, datetime):
        return None

    elif data.fqdn.casefold() != fqdn.casefold():
        return None

    return data


def remove_dns_record_state() -> None:
    """ Remove the state file from the state directory. NSUPDATE_LOCK must be held. """
    try:
        os.unlink(DS_DNS_STATE_FILE)
    except FileNotFoundError:
        pass


def dns_record_is_expired(fqdn: str) -> bool:
    """ Check whether our state is expired. NSUPDATE_LOCK must be held. """
    if not isinstance(fqdn, str):
        raise ValueError(f'{type(fqdn)}: unexpected type for host when checking DNS record expiration')

    if (data := __get_nsupdate_state(fqdn)) is None:
        # Either no nsupdate data or invalid data
        return True

    now = utc_now(False)
    return now > data.expiry


def update_dns_record_state(fqdn: str, expiry_time_delta: timedelta = DEFAULT_RECORD_EXPIRY) -> None:
    """ Update our state. NSUPDATE_LOCK must be held. """
    if not isinstance(fqdn, str):
        raise ValueError(f'{type(fqdn)}: unexpected type for host when updating DNS record state.')

    expiry = utc_now(False) + expiry_time_delta
    data = NSUpdateState(fqdn=fqdn, expiry=expiry, version=NSUPDATE_STATE_VERSION)
    write_if_changed(DS_DNS_STATE_FILE, json.dumps(asdict(data)))
