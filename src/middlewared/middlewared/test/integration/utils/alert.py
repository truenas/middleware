from .call import call


def process_alerts():
    call("alert.initialize")
    call("core.bulk", "alert.process_alerts", [[]], job=True)
