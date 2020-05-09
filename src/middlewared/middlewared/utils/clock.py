import ntplib
import datetime

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
            clock = response.tx_time
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
                clock = response.tx_time
                # Get the time, it could stop now
                break
                
        except Exception:
            # Cannot connect to the ntp server 
            pass 
    
    return clock
