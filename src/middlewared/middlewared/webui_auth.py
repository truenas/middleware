from ipaddress import ip_address, ip_network


def addr_in_allowlist(remote_addr, allowlist):
    valid = False
    try:
        remote_addr = ip_address(remote_addr)
    except Exception:
        # invalid/malformed IP so play it safe and
        # return False
        valid = False
    else:
        for allowed in allowlist:
            try:
                allowed = ip_network(allowed)
            except Exception:
                # invalid/malformed network so play it safe
                valid = False
                break
            else:
                if remote_addr == allowed or remote_addr in allowed:
                    valid = True
                    break

    return valid
