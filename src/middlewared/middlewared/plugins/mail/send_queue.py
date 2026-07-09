import logging

from middlewared.service import NetworkActivityDisabled, ServiceContext

from .message import from_addr
from .queue import MailQueue
from .send import sendmail

logger = logging.getLogger(__name__)


def send_mail_queue(context: ServiceContext, queue: MailQueue) -> None:
    with queue as mq:
        for item in list(mq.queue):
            try:
                config = context.call_sync2(context.s.mail.config)

                # Update `From` address from currently used config because if the SMTP user changes,
                # already queued messages might not be sent due to (553, b"Relaying disallowed as xxx")
                # error. `replace_header` because `__setitem__` appends a second `From` header instead
                # of replacing the existing one.
                item.message.replace_header("From", from_addr(config))

                sendmail(context, item.message, config)
            except NetworkActivityDisabled:
                # no reason to queue up email since network activity was explicitly denied by end-user
                mq.queue.remove(item)
            except Exception:
                logger.debug("Sending message from queue failed", exc_info=True)
                item.attempts += 1
                if item.attempts >= mq.MAX_ATTEMPTS:
                    mq.queue.remove(item)
            else:
                mq.queue.remove(item)
