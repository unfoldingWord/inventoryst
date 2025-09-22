from .Platform import Platform
from collections import OrderedDict


class Discourse(Platform):
    def __init__(self):
        super().__init__()

        # Loading configuration
        self.__config = self.load_config('discourse')

        self.discourse_api_host = self.__config['api_host']
        self.discourse_api_user = self.__config['api_user']
        self.discourse_api_key = self.__config['api_key']


    def __get_discourse_data(self, command):
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
        dict_return = dict()
        dict_return["meta"] = dict()
        dict_return["content"] = list()

        results = self.__get_discourse_data('groups.json')

        dict_return['meta']['group_count'] = len(results['groups'])

        field_filter = ['display_name', 'name', 'user_count', 'bio_raw', 'incoming_email']
        for group in results['groups']:
            t_group = self._filter_fields(group, field_filter)

            if 'display_name' not in group:
                t_group['display_name'] = group['full_name']

            dict_return['content'].append(t_group)

        return dict_return

    def __groups_to_markdown(self, groups):
        lst_content = list()

        lst_content.append(">[!info] General information")
        lst_content.append(self._item('Number of groups', groups['meta']['group_count']))
        lst_content.append('')

        # Sort alphabetically on the name
        groups_sorted = sorted(groups["content"], key=lambda item: item["name"])

        for group in groups_sorted:

            lst_content.append(f"- {group['name']} ({group['user_count']} users)")
            if group['bio_raw']:
                lst_content.append(f"  *{group['bio_raw']}*")
            if group['incoming_email']:
                lst_content.append(f"  **Incoming email**: {group['incoming_email'].replace('|', ', ')}")

        lst_content.append('')

        file = "discourse/groups.md"
        return {file: lst_content}

    def __get_user(self, t_id):
        trust_level = [
            'New user',
            'Basic user',
            'Member',
            'Regular',
            'Leader'
        ]

        dict_user = self.__get_discourse_data(f'admin/users/{t_id}.json')

        field_filter = ['username', 'name', 'avatar_template', 'admin', 'moderator', 'active', 'trust_level', 'created_at', 'last_seen_at']
        t_user = self._filter_fields(dict_user, field_filter)

        t_user['avatar'] = t_user['avatar_template'].replace('{size}', '64')
        t_user['trust_level'] = f"{trust_level[dict_user['trust_level']]} ({dict_user['trust_level']})"

        return t_user

    def __enumerate_users(self):
        dict_return = dict()
        dict_return["meta"] = dict()
        dict_return["content"] = list()

        lst_discourse_groups = sorted(self.__config['groups'])

        dict_users = dict()

        for group in lst_discourse_groups:
            # Get all members
            results = self.__get_discourse_data(f'groups/{group}/members.json')

            for user in results['members']:
                if user['id'] not in dict_users:
                    t_user = self.__get_user(user['id'])
                    t_user['groups'] = [group]

                    dict_users[user['id']] = t_user
                else:
                    dict_users[user['id']]['groups'].append(group)

        # Meta info
        dict_return["meta"] = {
            "user_count": len(dict_users),
            "user_count_active": len([user for user in dict_users.items() if user[1]['active'] is True]),
            "user_count_admin": len([user for user in dict_users.items() if user[1]['admin'] is True]),
            "user_count_moderator": len([user for user in dict_users.items() if user[1]['moderator'] is True]),
            "groups_scanned": ', '.join(lst_discourse_groups)
        }

        # Content
        dict_return['content'] = dict_users

        return dict_return

    def __users_to_markdown(self, dict_users):
        lst_content = list()

        lst_content.append(">[!info] General information")
        lst_content.append(self._item('Users', dict_users['meta']['user_count']))
        lst_content.append(self._item('Active users', dict_users['meta']['user_count_active']))
        lst_content.append(self._item('Admins', dict_users['meta']['user_count_admin']))
        lst_content.append(self._item('Moderators', dict_users['meta']['user_count_moderator']))
        lst_content.append(self._item('Groups scanned', dict_users['meta']['groups_scanned']))
        lst_content.append('')

        # Sort users alphabetically on username
        users_sorted = OrderedDict(sorted(dict_users["content"].items(), key=lambda item: item[1]["username"]))

        for _id, user in users_sorted.items():
            # Avatar
            if 'avatar' in user:
                style_overrides = {'width': '75px', 'height': '75px'}
                avatar = self._avatar(f'https://{self.discourse_api_host}{user["avatar"]}', style_overrides=style_overrides)
            else:
                avatar = ''

            if user['name'] == '':
                display_name = user['username']
            else:
                display_name = user['name'] + " (" + user['username'] + ")"

            # Paste avatar image in front of name for proper alignment
            lst_content.append(f'{avatar} {self._item('Name', display_name)}')

            lst_content.append(self._item('Created', self._format_date(user['created_at'])))
            lst_content.append(self._item('Last seen', self._format_date(user['last_seen_at'])))

            # Status
            status = "Active" if user['active'] else "Inactive"
            status_color = "green" if user['active'] else "#e94b45"
            lst_content.append(self._item('Status', self._highlight(status, status_color)))

            lst_content.append(self._item('Trust level', user['trust_level']))

            # Admin
            admin = "yes" if user['admin'] else "no"
            admin_color = "#4c82a9" if user['admin'] else ""
            admin_weight = "bold" if user['admin'] else "normal"
            lst_content.append(self._item('Admin', self._highlight(admin, admin_color, weight=admin_weight)))

            # Moderator
            moderator = "yes" if user['moderator'] else "no"
            mod_color = "#4c82a9" if user['moderator'] else ""
            mod_weight = "bold" if user['moderator'] else "normal"
            lst_content.append(self._item('Moderator', self._highlight(moderator, mod_color, weight=mod_weight)))

            lst_content.append(self._item('Groups', ', '.join(user['groups'])))
            lst_content.append('')

        file = "discourse/users.md"
        return {file: lst_content}

    def _build_content(self):
        md_main = dict()

        # Groups
        inventory = self.__enumerate_groups()
        md_main.update(self.__groups_to_markdown(inventory))

        # users
        inventory = self.__enumerate_users()
        md_main.update(self.__users_to_markdown(inventory))

        return md_main
