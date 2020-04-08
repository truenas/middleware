import json
import requests


class TruecommandAPIMixin:

    PORTAL_URI = 'https://portal.ixsystems.com/api'

    def _post_call(self, options=None, payload=None):
        options = options or {}
        timeout = options.get('timeout', 15)
        response = {'error': None, 'response': {}}
        try:
            req = requests.post(
                options.get('url', self.PORTAL_URI), data=json.dumps(payload or {}), timeout=timeout
            )
        except requests.exceptions.Timeout:
            response['error'] = f'Unable to connect with iX portal in {timeout} seconds.'
        else:
            try:
                req.raise_for_status()
            except requests.HTTPError as e:
                response['error'] = f'Error Code ({req.status_code}): {e}'
            else:
                response['response'] = req.json()
        return response
