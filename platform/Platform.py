import os
import requests
import datetime


class Platform:
    def __init__(self):
        self._now = datetime.datetime.now(tz=datetime.timezone.utc)

    def _get_json_from_url(self, url, token):
        # Basic headers
        req_headers = {
            'User-Agent': 'Inventoryst/1.0; https://github.com/unfoldingWord/inventoryst'
        }

        if token:
            req_headers['Authorization'] = 'Token ' + token
            raw = requests.get(url, headers=req_headers)
        # elif auth:
        #     req_headers['Authorization'] = auth
        #     raw = requests.get(url, headers=req_headers)
        else:
            raw = requests.get(url, headers=req_headers)

        return raw.json()

    def _get_output_dir(self):
        base_path = os.getenv('OUTPUT_DIRECTORY')
        if not base_path:
            # Assuming we're in Docker mode ;-)
            base_path = '/app/output'

        return base_path

    def _get_env(self, key):
        env_value = os.getenv(key)
        if not env_value:
            raise RuntimeError(f"Environment variable '{key}' not available")

        return env_value

    def _get_header_warning(self):
        str_message = (">[!warning] Important notice: this page is automatically generated\n"
                       ">Please be aware that this page is automatically generated and maintained by \
                       [Inventoryst](https://www.github.com/unfoldingword/inventoryst). "
                       "Any manual changes made to the content and layout will be overwritten during the next update. "
                       "If you have specific information or customization needs, please contact your \
                       System Administrator.\n"
                       )

        return str_message
