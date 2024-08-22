from .Platform import Platform


class Discourse(Platform):
    def __init__(self):
        super().__init__()

        self.discourse_api_host = self._get_env('DISCOURSE_API_HOST')
        self.discourse_api_user = self._get_env('DISCOURSE_API_USER')
        self.discourse_api_key = self._get_env('DISCOURSE_API_KEY')

    def get_discourse_data(self, command):
        # https://docs.discourse.org/

        discourse_url = f"https://{self.discourse_api_host}/{command}"

        headers = [
            ['Api-Username', self.discourse_api_user],
            ['Api-Key', self.discourse_api_key]
        ]

        dict_results = self._get_json_from_url(discourse_url, headers=headers)

        self._logger.debug(dict_results)

        return dict_results

    def __enumerate_groups(self):
        pass

    def __enumerate_users(self):
        lst_users = list()

        return lst_users

    def __users_to_markdown(self, lst_users):
        dict_users = dict()

        return dict_users

    def _build_content(self):
        md_main = dict()

        # domains
        inventory = self.__enumerate_users()
        md_main.update(self.__users_to_markdown(inventory))

        return md_main
