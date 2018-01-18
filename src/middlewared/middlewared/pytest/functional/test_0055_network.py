def test_network_interfaces_sync(conn):
    conn.ws.call('interfaces.sync')


def test_network_routes_sync(conn):
    conn.ws.call('routes.sync')


def test_network_dns_sync(conn):
    conn.ws.call('dns.sync')
