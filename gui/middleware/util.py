from freenasUI.middleware.client import client


def run_alerts():
    with client as c:
        c.call('alert.process_alerts')
