import datetime
import hashlib
import logging
import os
from dateutil import parser
import requests
import yaml

class Platform:
    def __init__(self):
        self._now = datetime.datetime.now(tz=datetime.timezone.utc)

        # Load configuration
        self.__config = self.load_config('general')
        self._stage = self.__config['stage']

        # Init logging
        self._logger = logging.getLogger()

        # Misc
        self.__page_properties = dict()
        self.__pages_changed = 0
        self.__api_calls = 0

    def _get_json_from_url(self, url, headers=None, data=None, raw=False, auth=None, connection=None):
        # Basic headers
        req_headers = {
            'User-Agent': 'Inventoryst/1.0; https://github.com/unfoldingWord/inventoryst'
        }

        if not connection:
            connection = requests

        if headers:
            for header in headers:
                req_headers[header[0]] = header[1]

        if data is None:
            result = connection.get(url, headers=req_headers, auth=auth)
        else:
            result = connection.post(url, json=data, headers=req_headers, auth=auth)

        self._inc_api_call()
        self._logger.debug(result)

        if raw:
            return result
        elif result:
            return result.json()
        else:
            return None

    @staticmethod
    def load_config(platform):
        # YAML file path
        yaml_file = 'inventoryst.yaml'

        # Reading YAML data from file
        with open(yaml_file, 'r') as f:
            return yaml.safe_load(f)[platform]

    def get_changed_page_count(self):
        return self.__pages_changed

    def get_api_calls(self):
        return self.__api_calls

    def _inc_api_call(self, incr=1):
        self.__api_calls += incr

    def _get_output_dir(self):
        base_path = self.__config['output_directory']
        if not base_path:
            # Assuming we're in Docker mode ;-)
            base_path = '/app/output'

        return base_path

    def _filter_fields(self, data, field_filter):

        if hasattr(data, '__dict__'):
            return {item: eval(f"data.{item}") for item in field_filter}
        elif type(data) == dict:
            return {k: v for k, v in data.items() if k in field_filter}

    def _get_env(self, key):
        env_value = os.getenv(key)
        if not env_value:
            raise RuntimeError(f"Environment variable '{key}' not available")

        return env_value

    def _link(self, target, caption='', internal=False):
        if internal is True:
            return f"[[{target}|{caption}]]"

        return f"[{caption}]({target})"

    def _highlight(self, text, color, background='', weight='bold', border_color=''):
        # Build the style
        dict_style = {
            'color': color,
            'font-weight': weight,
            'padding': '1px'
        }
        if background:
            dict_style['background'] = background
        if border_color:
            dict_style['border'] = f'1px solid {border_color}'

        # Make it a string and return it
        style="; ".join([f"{k}: {v}" for k, v in dict_style.items()])
        return f"<span style=\"{style}\">{text}</span>"

    def _item(self, name, value, prefix='', indent=0):
        # An item is a name, followed by colon and then the value
        return f"{prefix}{' ' * indent}**{name}:** {value}"

    def _note(self, text):
        # A note is italic
        return f'*{text}*'

    def _header(self, title, size=2):
        return f"{('#' * size)} {title}"

    def _format_date(self, tdate):
        date_format = "%a, %b %-d, %Y, %-I:%M %p"
        if type(tdate) is datetime.datetime:
            return tdate.strftime(date_format)
        elif type(tdate) is int:
            return datetime.datetime.fromtimestamp(tdate).strftime(date_format)

        return parser.parse(tdate).strftime(date_format)

    def _avatar(self, content: str, avatar_type='image', style_overrides=dict()):
        dict_avatar_style = {
            'display': 'block',
            'object-fit': 'cover',
            'border-radius': '100%',
            'width': '50px',
            'height': '50px',
            'float': 'left',
            'margin-right': '10px'
        }

        if avatar_type != 'image':
            dict_avatar_style['background'] = 'gray'
            dict_avatar_style['font-size'] = '25px'
            dict_avatar_style['padding-top'] = '5px'
            dict_avatar_style['text-align'] = 'center'

        if len(style_overrides):
            dict_avatar_style.update(style_overrides)

        avatar_style = '; '.join([f'{key}: {dict_avatar_style[key]}' for key in dict_avatar_style])

        if avatar_type == 'image':
            return f'<img src="{content}" style="{avatar_style}" />'
        else:
            return f'<span style="{avatar_style}">{content}</span>'

    def _pull_initials(self, name):
        parts = name.split()
        initials = "".join([part[0] for part in parts]).upper()

        return initials

    def _format_bytes(self, size, rounding=2):
        # 2**10 = 1024
        power = 2 ** 10
        n = 0
        power_labels = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
        while size > power:
            size /= power
            n += 1

        return str(round(size, rounding)) + ' ' + power_labels[n] + 'B'

    def _add_page_property(self, key, value):
        self.__page_properties[key] = value

    def __get_page_properties(self):
        if len(self.__page_properties):
            properties = ''
            for tproperty, value in self.__page_properties.items():

                if type(value) is list:
                    value = '\n'.join(['  - ' + item for item in value])
                    properties += tproperty + ': \n' + value + '\n'
                else:
                    properties += tproperty + ': ' + value + "\n"

            self._logger.debug(properties.replace('\n', '/'))
            return "---\n" + properties + "---\n"
        else:
            # Return empty property block.
            # This only occurs when checking if a page is modified. When we actually write the page,
            # it will always contain at least the 'modified' property
            return "---\n" + "---\n"

    def __get_header_warning(self):
        str_message = (">[!warning] Important notice: this page is automatically generated\n"
                       ">Please be aware that this page is automatically generated and maintained by "
                       "[Inventoryst](https://www.github.com/unfoldingword/inventoryst). "
                       "Any manual changes made to the content and layout will be overwritten during the next update. "
                       "If you have specific information or customization needs, please contact your "
                       "System Administrator.\n"
                       )

        return str_message

    def __prep_page_content(self, main_content):
        lst_page_content = list()
        if self.__get_page_properties():
            lst_page_content.append(self.__get_page_properties())
        lst_page_content.append(self.__get_header_warning() + "\n")
        lst_page_content.append("\n".join(main_content))
        new_content = "".join(lst_page_content)

        return new_content

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
            new_content = self.__prep_page_content(inventory[page])

            # Generate hash for new content
            hash_new = hashlib.sha256(new_content.encode()).hexdigest()
            self._logger.debug("New hash: " + hash_new)

            f_path = base_path + "/" + page
            hash_old = ""
            if os.path.exists(f_path):
                with open(f_path, 'r') as file:
                    lst_old_content = list()

                    # Get all lines and collate them together
                    for line in file:
                        if line.find('modified: ') == -1:  # Ignore 'modified' line
                            lst_old_content.append(line)

                    old_content = "".join(lst_old_content)

                    # Generate hash for existing content
                    hash_old = hashlib.sha256(old_content.encode()).hexdigest()

                    self._logger.debug("Old hash: " + hash_old)
                    file.close()

            if os.path.exists(f_path) is False or (not hash_old == hash_new):
                if os.path.exists(f_path) is False:
                    self._logger.info(f"The page '{page}' has been created.")
                else:
                    self._logger.info(f"Page content for '{page}' has changed. Updating...")

                with open(base_path + "/" + page, 'w') as md_file:
                    # Last updated
                    self._add_page_property('modified', datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d"))
                    new_content = self.__prep_page_content(inventory[page])

                    md_file.write(new_content)

                    self.__pages_changed += 1

            else:
                self._logger.info(f"No changes for page '{page}'")

    def _build_content(self):
        raise NotImplementedError("You must override _build_content in your child class")

    def inventorize(self):
        inventory = self._build_content()
        self.__export_to_markdown_files(inventory)
