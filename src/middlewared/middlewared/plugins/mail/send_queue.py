import logging

from middlewared.service import NetworkActivityDisabled, ServiceContext

from .message import from_addr
from .queue import MailQueue
from .send import sendmail

logger = logging.getLogger(__name__)


def send_mail_queue(context: ServiceContext, queue: MailQueue) -> None:
    # `queue.lock` must not be held while delivering, or a `mail.send` that fails would block on it
    # for as long as this flush takes (up to `MAX_QUEUE_LIMIT` messages, each with its own timeout).
    # `send_lock` takes over the job of keeping two flushes from delivering the same message twice.
    if not queue.send_lock.acquire(blocking=False):
        logger.debug("Mail queue is already being flushed")
        return

    try:
        with queue as mq:
            items = list(mq.queue)

        done = []
        for item in items:
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
                done.append(item)
            except Exception:
                logger.debug("Sending message from queue failed", exc_info=True)
                item.attempts += 1
                if item.attempts >= queue.MAX_ATTEMPTS:
                    done.append(item)
            else:
                done.append(item)

        with queue as mq:
            for item in done:
                try:
                    mq.queue.remove(item)
                except ValueError:
                    # `queue` holds at most `MAX_QUEUE_LIMIT` messages and drops the oldest to make
                    # room, so a `mail.send` that failed while we were delivering may already have
                    # pushed `item` out.
                    pass
    finally:
        queue.send_lock.release()
