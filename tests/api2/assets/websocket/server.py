from time import sleep

from functions import make_ws_request, ping_host


def reboot(ip, service_name=None):
    """Reboot the TrueNAS at the specified IP.
    Return when it has rebooted."""
    # Reboot
    payload = {
        'msg': 'method', 'method': 'system.reboot',
        'params': []
    }
    res = make_ws_request(ip, payload)
    assert res.get('error') is None, res
    # Wait for server to disappear
    sleep(5)
    TotalWait = 120  # 3 min
    while TotalWait > 0 and ping_host(ip, 1) is True:
        sleep(1)
        TotalWait -= 1
    assert ping_host(ip, 1) is not True
    # Wait for server to return
    sleep(10)
    TotalWait = 120  # 3 min
    while TotalWait > 0 and ping_host(ip, 1) is not True:
        sleep(1)
        TotalWait -= 1
    assert ping_host(ip, 1) is True
    # ip returns before websocket connection is ready
    # Wait a few more seconds
    sleep(10)

    if service_name:
        TotalWait = 60  # 1 min
        payload = {
            'msg': 'method', 'method': 'service.query',
            'params': [['service', '=', service_name]]
        }
        while TotalWait > 0:
            try:
                res = make_ws_request(ip, payload)
                if res.get('error') is None:
                    print(res)
            except Exception:
                pass
            sleep(1)
            TotalWait -= 1
        assert False, f"Failed to detect {service_name} as running following reboot"
