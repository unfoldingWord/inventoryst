from .Platform import Platform
import os
import base64
import requests
from dateutil import parser as date_parser
import pprint


class Zoom(Platform):
    def __init__(self):
        super().__init__()

        self.access_token = self.__request_access_token()

    def __request_access_token(self):
        account_id = os.getenv('ZOOM_ACCOUNT_ID')
        client_id = os.getenv('ZOOM_CLIENT_ID')
        client_secret = os.getenv('ZOOM_CLIENT_SECRET')
        zoom_api = 'https://zoom.us/oauth/token'

        encoded_auth = base64.b64encode((client_id + ":" + client_secret).encode('utf-8')).decode('utf-8')
        #print(encoded_auth)

        dict_headers = dict()
        dict_headers['Content-Type'] = "application/x-www-form-urlencoded"
        dict_headers['Authorization'] = "Basic " + str(encoded_auth)

        dict_post_data = dict()
        dict_post_data['grant_type'] = 'account_credentials'
        dict_post_data['account_id'] = account_id

        response = requests.post(zoom_api, dict_post_data, headers=dict_headers)

        return response.json()['access_token']

    def __make_api_request(self, api_url):

        dict_headers = dict()
        dict_headers['Content-Type'] = "application/x-www-form-urlencoded"
        dict_headers['Authorization'] = "Bearer " + self.access_token

        qs = '?page_size=100'

        response = requests.get(api_url + qs, headers=dict_headers)
        return response.json()

    def __enumerate_users(self):
        dict_users = dict()
        dict_users["meta"] = dict()
        dict_users["content"] = list()

        users = self.__make_api_request('https://api.zoom.us/v2/users')
        # pprint.pprint(users)
        # exit()

        dict_users["meta"]["user_count"] = users['total_records']

        nr_of_admins = len([admin for admin in users['users'] if admin['role_id'] == '1'])
        dict_users["meta"]["admin_count"] = nr_of_admins

        for user in users['users']:

            tmp_user = dict()
            tmp_user['id'] = user['id']
            tmp_user['full_name'] = user['first_name'] + ' ' + user['last_name']
            tmp_user['display_name'] = user['display_name']
            tmp_user['email'] = user['email']
            tmp_user['pmi'] = user['pmi']
            if 'last_client_version' in user:
                tmp_user['last_client_version'] = user['last_client_version']
            tmp_user['last_login'] = user['last_login_time']
            tmp_user['verified'] = user['verified']
            tmp_user['type'] = user['type']
            tmp_user['role_id'] = user['role_id']
            if 'pic_url' in user:
                tmp_user['avatar'] = user['pic_url']

            dict_users['content'].append(tmp_user)

        return dict_users

    def __users_to_markdown(self, inventory):

        lst_content = list()

        lst_content.append(">[!info] General information")
        lst_content.append(f">**Overview:** [Users](https://us02web.zoom.us/account/user#/)")
        lst_content.append("**Number of users:** " + str(inventory["meta"]["user_count"]))
        lst_content.append("**Number of admins:** " + str(inventory["meta"]["admin_count"]))

        lst_content.append("")

        lst_users = sorted(inventory["content"], key=lambda item: item["full_name"])

        for dict_user in lst_users:
            if 'avatar' in dict_user:
                avatar = '<img src="' + dict_user['avatar'] + '" style="width: 75px; float: left; margin-right: 10px" />'
            else:
                avatar = ''

            if dict_user['full_name'] == dict_user['display_name']:
                display_name = dict_user['full_name']
            else:
                display_name = dict_user['full_name'] + " (" + dict_user['display_name'] + ")"
            # Paste avatar image in front of name for proper alignment
            lst_content.append(avatar + "**Name:** " + display_name)

            lst_content.append("**PMI:** " + str(dict_user['pmi']))
            lst_content.append("**Email:** " + dict_user['email'])

            last_login = date_parser.parse(dict_user['last_login']).strftime("%a, %b %-d, %Y, %-I:%M %p")
            lst_content.append("**Last login:** " + last_login)

            if 'last_client_version' in dict_user:
                lst_content.append("**Last client:** " + dict_user['last_client_version'])

            if dict_user['type'] == 2:
                lic_type = "Licensed"
            else:
                lic_type = "Basic"
            lst_content.append("**Type:** " + lic_type)

            if dict_user['role_id'] == '1':
                role = 'Admin'
            else:
                role = 'Member'
            lst_content.append("**Role:** " + role)

            lst_content.append("")






        file = "zoom/users.md"
        return {file: lst_content}

    def _build_content(self):
        md_main = dict()

        # users
        inventory = self.__enumerate_users()
        md_main.update(self.__users_to_markdown(inventory))

        # users
        # inventory = self.__enumerate_users()
        # md_main.update(self.__users_to_markdown(inventory))

        return md_main


