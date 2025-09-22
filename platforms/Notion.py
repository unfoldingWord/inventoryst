import os
from .Platform import Platform
import pprint

class Notion(Platform):

    def __init__(self):
        super().__init__()

        self.__api_url = 'https://api.notion.com/v1'
        self.__internal_api_url = 'https://www.notion.so/api/v3'
        self.__api_key = self.load_config('notion')['integration_secret']
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


    def __markdown_users(self, dict_users):
        lst_content = list()

        lst_content.append(">[!info] General information")
        lst_content.append(self._item('Number of persons', dict_users["meta"]["nr_of_persons"]))
        lst_content.append(self._item('Number of bots', dict_users["meta"]["nr_of_bots"]))
        lst_content.append("")

        # Pull out all persons
        lst_persons = [user for user in dict_users['content'] if user['type'] == 'person']

        # Pull out all bots
        lst_bots = [user for user in dict_users['content'] if user['type'] == 'bot']

        # Persons
        # Sort persons on name
        persons_sorted = sorted(lst_persons, key=lambda item: item["name"])

        lst_content.append(self._header('Persons'))
        lst_content.append("")
        for user in persons_sorted:

            if user['avatar_url'] is not None:
                avatar = self._avatar(user['avatar_url'])
            else:
                parts = user['name'].split()
                initials = "".join([part[0] for part in parts]).upper()

                avatar = self._avatar(initials, avatar_type='text')

            lst_content.append(f"{avatar}**{user['name']}**")
            lst_content.append(self._item('ID', user['id']))
            lst_content.append(self._item('Type', 'person'))
            lst_content.append(self._item('Email', user['person']['email']))
            lst_content.append("")

        # Bots
        # Sort bots on name
        bots_sorted = sorted(lst_bots, key=lambda item: item["name"])

        lst_content.append(self._header('Bots'))
        lst_content.append("")

        for user in bots_sorted:

            if user['avatar_url'] is not None:
                avatar = self._avatar(user['avatar_url'])
            else:
                parts = user['name'].split()
                initials = "".join([part[0] for part in parts]).upper()

                avatar = self._avatar(initials, avatar_type='text')

            lst_content.append(f"{avatar}**{user['name']}**")
            lst_content.append(self._item('ID', user['id']))
            lst_content.append(self._item('Type', 'bot'))
            lst_content.append("")

        file = "notion.md"
        return {file: lst_content}

    def _build_content(self):
        md_main = dict()

        users = self.__enumerate_users()
        md_main.update(self.__markdown_users(users))

        return md_main
