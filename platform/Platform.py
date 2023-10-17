import os
import requests
import datetime


class Platform:
    def __init__(self):
        self._now = datetime.datetime.now(tz=datetime.timezone.utc)

    def _get_json_from_url(self, url, authorization):
        # Basic headers
        req_headers = {
            'User-Agent': 'Inventoryst/1.0; https://github.com/unfoldingWord/inventoryst'
        }

        if authorization:
            req_headers['Authorization'] = authorization
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

    def __export_to_markdown_files(self, inventory):
        base_path = self._get_output_dir()

        if not os.path.exists(base_path):
            raise FileExistsError(f"The directory '{base_path}' does not exist. Exiting.")

        for page in inventory:
            print(page)
            # We need to do magic stuff with paths and files here

            with open(base_path + "/" + page, 'w') as md_file:
                # Last updated
                str_date = datetime.datetime.utcnow().strftime("%B %d %Y, %I:%M %p")
                md_file.write("*Last updated: " + str_date + "*\n")

                # Add generic warning
                md_file.write(self._get_header_warning() + "\n")

                str_content = "\n".join(inventory[page])
                md_file.write(str_content)

    def _build_content(self):
        raise NotImplementedError("You must override _build_content in your child class")

    def inventorize(self):
        inventory = self._build_content()
        self.__export_to_markdown_files(inventory)
