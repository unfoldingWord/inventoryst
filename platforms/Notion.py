import os
from .Platform import Platform
import pprint

class Notion(Platform):

    def __init__(self):
        super().__init__()

        self.__api_url = 'https://api.notion.com/v1'
        self.__internal_api_url = 'https://www.notion.so/api/v3'
        self.__api_key = self._get_env('NOTION_INTEGRATION_SECRET')
        self.__headers = [
            ['Authorization', 'Bearer ' + self.__api_key],
            ['Notion-Version', '2022-06-28'],
        ]

    def __enumerate_users(self):
        dict_users = dict()
        dict_users["meta"] = dict()
        dict_users["content"] = list()

        url_users = f'{self.__api_url}/users'
        lst_users = self._get_json_from_url(url=url_users, headers=self.__headers)

        nr_of_bots = 0
        nr_of_persons = 0

        if lst_users:
            for user in lst_users['results']:
                if user['type'] == 'person':
                    nr_of_persons += 1
                else:
                    nr_of_bots += 1

            dict_users['meta']['nr_of_bots'] = nr_of_bots
            dict_users['meta']['nr_of_persons'] = nr_of_persons

            dict_users['content'] = lst_users['results']

        return dict_users


    def __users_to_markdown(self, dict_users):
        lst_content = list()

        lst_content.append(">[!info] General information")
        lst_content.append("**Number of persons:** " + str(dict_users["meta"]["nr_of_persons"]))
        lst_content.append("**Number of bots:** " + str(dict_users["meta"]["nr_of_bots"]))
        lst_content.append("")

        avatar_style = 'display: block; object-fit: cover; border-radius: 100%; width: 50px; \
                        height: 50px; float: left; margin-right: 10px;'

        # Pull out all persons
        lst_persons = [user for user in dict_users['content'] if user['type'] == 'person']

        # Pull out all bots
        lst_bots = [user for user in dict_users['content'] if user['type'] == 'bot']

        # Persons
        # Sort persons on name
        persons_sorted = sorted(lst_persons, key=lambda item: item["name"])

        lst_content.append("## Persons")
        lst_content.append("")
        for user in persons_sorted:

            if user['avatar_url'] is not None:
                avatar = f'<img src="{user['avatar_url']}" style="{avatar_style}" />'
            else:
                parts = user['name'].split()
                initials = "".join([part[0] for part in parts]).upper()

                avatar = f'<span style="{avatar_style} background: gray; font-size: 25px; padding-top: 5px; text-align: center;">{initials}</span>'

            lst_content.append(f"{avatar}**{user['name']}**")
            lst_content.append(f"**ID:** {user['id']}")
            lst_content.append("**Type:** person")
            lst_content.append(f"**Email:** {user['person']['email']}")
            lst_content.append("")

        # Bots
        # Sort bots on name
        bots_sorted = sorted(lst_bots, key=lambda item: item["name"])

        lst_content.append("## Bots")
        lst_content.append("")

        for user in bots_sorted:

            if user['avatar_url'] is not None:
                avatar = f'<img src="{user['avatar_url']}" style="{avatar_style}" />'
            else:
                parts = user['name'].split()
                initials = "".join([part[0] for part in parts]).upper()

                avatar = f'<span style="{avatar_style} background: gray; font-size: 25px; padding-top: 5px; text-align: center;">{initials}</span>'

            lst_content.append(f"{avatar} **{user['name']}**")
            lst_content.append(f"**ID:** {user['id']}")
            lst_content.append("**Type:** bot")
            lst_content.append("")

        file = "notion.md"
        return {file: lst_content}

    def _build_content(self):
        md_main = dict()

        users = self.__enumerate_users()
        md_main.update(self.__users_to_markdown(users))

        return md_main
