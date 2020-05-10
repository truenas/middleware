import ntplib
from datetime import datetime, timezone


def _convert_datetime(response, timezone_setting=timezone.utc):
    return datetime.fromtimestamp(response.tx_time, timezone_setting)

# Sync the clock
def sync_clock(middleware):
    
    client = ntplib.NTPClient()
    server_alive = False
    clock = None
    
    # Tries to get default ntpd server
    try:
        response = client.request("localhost")
        if response.version:
            server_alive = True
            clock = _convert_datetime(response)
    except Exception:
        # Cannot connect to NTP server 
        pass  
    
    if clock is not None: 
        return clock

    # If it fails, tries the list of default ntp servers configurable
    ntp_servers = middleware.call_sync('system.ntpserver.query')
    for server in ntp_servers:
        try:
            response = client.request(server)
            if response.version:
                server_alive = True
                clock = _convert_datetime(response)
                # Get the time, it could stop now
                break
                
        except Exception:
            # Cannot connect to the ntp server 
            pass 
    
    return clock
