from email.header import Header
from email.utils import formataddr

from middlewared.api.current import MailEntry


def from_addr(config: MailEntry) -> str:
    if config.fromname:
        pair = (config.fromname, config.fromemail)
        try:
            return formataddr(pair, "ascii")
        except UnicodeEncodeError:
            return formataddr(pair, "utf-8")
    else:
        try:
            config.fromemail.encode("ascii")
        except UnicodeEncodeError:
            from_addr = Header(config.fromemail, "utf-8")
        else:
            from_addr = Header(config.fromemail, "ascii")

        return from_addr.encode()
