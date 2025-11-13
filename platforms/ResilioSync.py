from .Platform import Platform
import requests
import time
from pprint import pp
import re

class ResilioSync(Platform):
    def __init__(self):
        super().__init__()

        # Load config
        self.__config = self.load_config('resiliosync')

        self.__connection = self.__login()
        self.__api_url = f"{self.__config['host_url']}/gui"
        self.__token = self.__get_token()

    def __login(self):
        session = requests.Session()
        session.cert = (self.__config['user_certificate'], self.__config['user_key'])
        session.auth = (self.__config['username'], self.__config['password'])

        session.get(self.__config['host_url'])

        return session

    def __build_action_url(self, action):
        ts = int(time.time() * 1000)
        url = f'{self.__api_url}/?token={self.__token}&action={action}&discovery=1&t={ts}'
        return url

    def __get_token(self):
        ts = int(time.time() * 1000)
        url = f'{self.__api_url}/token.html?t={ts}'

        token_data = self._get_json_from_url(url, connection=self.__connection, raw=True).content

        # Extract token from HTML code
        token = re.match(r"<html><div id='token' style='display:none;'>(.+)</div></html>", token_data.decode('utf-8'))[1]

        return token

    def __access_int_to_text(self, access):
        dict_access_map = {
            2 : 'Read Only',
            3 : 'Read & Write',
            4 : 'Owner'
        }

        return dict_access_map[access]

    def __enumerate_sync_folders(self):
        dict_folders = dict()
        dict_folders['meta'] = dict()
        dict_folders['content'] = list()

        url_folders = self.__build_action_url('getsyncfolders')

        folder_filter = ['name', 'archive_files', 'archive_size', 'local_files', 'local_size']

        folders = self._get_json_from_url(url_folders, connection=self.__connection)['folders']
        dict_folders['meta']['folder_count'] = len(folders)

        for folder in folders:
            dict_folder = self._filter_fields(folder, folder_filter)

            # 'Merge' users and peers
            users = sorted(folder['users'], key=lambda d: d['name'].lower())

            t_users = list()
            for user in users:
                peered = next((item for item in folder['peers'] if item["userid"] == user['id']), None)
                if peered:
                    user['active'] = True
                    user['peer_name'] = peered['name']

                    activity_time = 0
                    if 'lastseentime' in peered:
                        activity_time = peered['lastseentime']
                    elif 'lastsynctime' in peered:
                        activity_time = peered['lastsynctime']

                    user['last_activity_time'] = activity_time
                else:
                    user['active'] = False

                t_users.append(user)

            dict_folder['users'] = t_users

            dict_folders['content'].append(dict_folder)

        return dict_folders

    def __markdown_folders(self, folders):
        lst_content = list()

        # Info block
        lst_content.append(">[!info] General information")
        lst_content.append(self._item('Folders', folders['meta']['folder_count']))

        for folder in folders['content']:
            lst_content.append(self._header(folder['name']))
            lst_content.append(self._item('Items', folder['local_files']))
            lst_content.append(self._item('Size', self._format_bytes(folder['local_size'])))
            lst_content.append(self._item('Archive items', folder['archive_files']))
            lst_content.append(self._item('Archive size', self._format_bytes(folder['archive_size'])))
            lst_content.append('**Users**')
            for user in folder['users']:
                active = ''
                if user['active'] is True:
                    active = self._highlight('Active', '#add8e6', border_color='#add8e6')

                lst_content.append(f'- {self._item('Name', user['name'])} {active}')
                lst_content.append(f'  {self._item('Permissions', self.__access_int_to_text(user['access']))}')

                if user['active'] is True:
                    lst_content.append(f'  {self._item('Device', user['peer_name'])}')
                    lst_content.append(f'  {self._item('Last seen', self._format_date(user['last_activity_time']))}')

        file = f"resiliosync.md"
        return {file: lst_content}

    def _build_content(self):
        md_main = dict()

        sync_folders = self.__enumerate_sync_folders()
        md_main.update(self.__markdown_folders(sync_folders))

        return md_main

