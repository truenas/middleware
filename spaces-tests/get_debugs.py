import requests
import sys
from config import SPACES_CONFIG
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils import spaces_connections


def download_debug(c, member, results_dir):
    # query for existing zpool (clean CI run creates a zpool)
    print(f'Checking for existing zpools on {member.ip}')
    where = None
    try:
        where = "generate debug"
        job_id, path = c.call('core.download', 'system.debug', [], f'debug_node_{member.node}')
        r = requests.get(f'http://{member.ip}{path}')
        r.raise_for_status()
        filename = f'{results_dir}/node_{member.node}.tgz'
        print(f'Writing debug to {filename}')
        with open(filename, 'wb') as f:
            f.write(r.content)

    except Exception as e:
        return {'error': e, 'where': where, 'node': member.node, 'ip': member.ip}

    return {'result': filename, 'node': member.node, 'ip': member.ip}


def init(results_path):
    with spaces_connections() as connections:
        with ThreadPoolExecutor() as exc:
            # First, setup the network
            futures = [exc.submit(download_debug, *c, results_path) for c in connections]
            for fut in as_completed(futures):
                res = fut.result()
                if res.get('error'):
                    print(f'Node {res["node"]}, address {res["ip"]}: Failed to generate debug [{res["where"]}]: {res["error"]}')
                    sys.exit(2)
                else:
                    print(f'{res["result"]}: Node {res["node"]}, address {res["ip"]}: debug completed')
