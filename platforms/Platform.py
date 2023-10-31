import datetime
import hashlib
import logging
import os

import requests


class Platform:
    def __init__(self):
        self._now = datetime.datetime.now(tz=datetime.timezone.utc)

        # Init logging
        self._logger = logging.getLogger()

    @staticmethod
    def _get_json_from_url(url, authorization=None):
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
                       ">Please be aware that this page is automatically generated and maintained by "
                       "[Inventoryst](https://www.github.com/unfoldingword/inventoryst). "
                       "Any manual changes made to the content and layout will be overwritten during the next update. "
                       "If you have specific information or customization needs, please contact your "
                       "System Administrator.\n"
                       )

        return str_message

    def __export_to_markdown_files(self, inventory):
        base_path = self._get_output_dir()

        if not os.path.exists(base_path):
            raise FileExistsError(f"The output directory '{base_path}' does not exist. Exiting.")

        for page in inventory:
            self._logger.debug("Page: " + page)

            # Create path if it does not exist
            path = "/".join(page.split('/')[:-1])
            if not os.path.exists(base_path + "/" + path):
                os.makedirs(base_path + "/" + path)

            # Prep page content
            lst_page_content = list()
            lst_page_content.append(self._get_header_warning() + "\n")
            lst_page_content.append("\n".join(inventory[page]))
            new_content = "".join(lst_page_content)

            # Generate hash for new content
            hash_new = hashlib.sha256(new_content.encode()).hexdigest()
            self._logger.debug("New hash: " + hash_new)

            f_path = base_path + "/" + page
            hash_old = ""
            if os.path.exists(f_path):
                with open(f_path, 'r') as file:
                    lst_old_content = list()

                    # skip line with 'Last updated' statement (because it always changes)
                    next(file)

                    # Get all lines and collate them together
                    for line in file:
                        lst_old_content.append(line)

                    old_content = "".join(lst_old_content)

                    # Generate hash for existing content
                    hash_old = hashlib.sha256(old_content.encode()).hexdigest()

                    self._logger.debug("Old hash: " + hash_old)
                    file.close()

            if os.path.exists(f_path) is False or (not hash_old == hash_new):
                if os.path.exists(f_path) is False:
                    self._logger.info(f"The file '{page}' has been created.")
                else:
                    self._logger.info(f"Page content for '{page}' changed. Updating...")

                with open(base_path + "/" + page, 'w') as md_file:
                    # Last updated
                    str_date = datetime.datetime.utcnow().strftime("%B %d %Y, %I:%M %p")
                    md_file.write("*Last updated: " + str_date + "*\n")

                    md_file.write(new_content)
            else:
                self._logger.debug(f"No changes for page '{page}'")

    def _build_content(self):
        raise NotImplementedError("You must override _build_content in your child class")

    def inventorize(self):
        inventory = self._build_content()
        self.__export_to_markdown_files(inventory)
