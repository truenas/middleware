import datetime
import math

from .status_utils import Status


CERT_RENEW_DAYS = 5
CLAIM_TOKEN_CACHE_KEY = 'truenas_connect_claim_token'
CONFIGURED_TNC_STATES = (
    Status.CONFIGURED.name,
    Status.CERT_RENEWAL_IN_PROGRESS.name,
    Status.CERT_RENEWAL_SUCCESS.name,
)


def get_account_id_and_system_id(config: dict) -> dict | None:
    jwt_details = config['registration_details'] or {}
    if all(jwt_details.get(k) for k in ('account_id', 'system_id')) is False:
        return None

    return {
        'account_id': jwt_details['account_id'],
        'system_id': jwt_details['system_id'],
    }


def get_unset_payload() -> dict:
    return {
        'registration_details': {},
        'jwt_token': None,
        'status': Status.DISABLED.name,
        'certificate': None,
        'last_heartbeat_failure_datetime': None,
    }


def calculate_sleep(failure_dt_str: str | None) -> int | None:
    """
    Calculates the number of seconds to sleep before the next retry.

    Behavior:
      - If no failure datetime is provided, returns 5 seconds.
      - If the provided datetime is in the future, returns None.
      - If more than 48 hours have elapsed since the failure datetime, returns None.
      - Otherwise, uses an exponential backoff schedule:
          * First 3 attempts use a sleep time of 5 seconds.
          * Next 3 attempts use a sleep time of 10 seconds.
          * Next 3 attempts use a sleep time of 20 seconds, and so on.

        Within each group, the next attempt is scheduled exactly
        at group_interval seconds after the previous attempt.
        If the calculated sleep time is 0 or negative (i.e. we’re past the scheduled time),
        returns None (meaning no sleep is needed; try immediately).
    """
    base_sleep = 5

    # If no failure datetime is provided, return base_sleep.
    if not failure_dt_str:
        return base_sleep

    try:
        # Parse the failure datetime (expects ISO format).
        first_failure = datetime.datetime.fromisoformat(failure_dt_str)
    except Exception as e:
        raise ValueError(f'Invalid datetime string: {failure_dt_str}') from e

    now = datetime.datetime.now(tz=datetime.timezone.utc)

    # If the given failure time is in the future, return None.
    if first_failure > now:
        return None

    elapsed = (now - first_failure).total_seconds()
    max_elapsed = 48 * 3600  # maximum elapsed time threshold: 48 hours

    # If more than 48 hours have passed, no sleep is required.
    if elapsed > max_elapsed:
        return None

    # Determine the retry group based on elapsed time.
    # Each group has 3 attempts, each separated by a sleep interval.
    group = 0
    cumulative = 0  # cumulative time in seconds of all complete groups before the current group

    while True:
        # Sleep interval for the current group
        group_sleep = base_sleep * (2 ** group)
        # Total time allotted for 3 attempts in the current group
        group_total = 3 * group_sleep

        if elapsed < cumulative + group_total:
            # Determine the number of attempts already done within this group.
            attempt_in_group = int((elapsed - cumulative) // group_sleep)
            # The next attempt is scheduled after (attempt_in_group + 1) intervals in the group.
            next_attempt_time = cumulative + (attempt_in_group + 1) * group_sleep

            sleep_needed = next_attempt_time - elapsed
            # If the scheduled retry time has already passed, return None.
            if sleep_needed <= 0:
                return None
            else:
                return int(math.ceil(sleep_needed))
        else:
            cumulative += group_total
            group += 1
