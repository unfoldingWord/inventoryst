from .Platform import Platform
from collections import OrderedDict


class Discourse(Platform):
    def __init__(self):
        super().__init__()

        self.discourse_api_host = self._get_env('DISCOURSE_API_HOST')
        self.discourse_api_user = self._get_env('DISCOURSE_API_USER')
        self.discourse_api_key = self._get_env('DISCOURSE_API_KEY')

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

        for group in results['groups']:
            t_group = dict()
            t_group['display_name'] = group['display_name'] if 'display_name' in group else group['full_name']
            t_group['name'] = group['name']
            t_group['nr_of_users'] = group['user_count']
            t_group['description'] = group['bio_raw']
            t_group['incoming_email'] = group['incoming_email']

            dict_return['content'].append(t_group)

        return dict_return

    def __groups_to_markdown(self, groups):
        lst_content = list()

        lst_content.append(">[!info] General information")
        lst_content.append(f">**Number of groups:** {groups['meta']['group_count']}")
        lst_content.append('')

        # Sort alphabetically on the name
        groups_sorted = sorted(groups["content"], key=lambda item: item["name"])

        for group in groups_sorted:

            lst_content.append(f"- {group['name']} ({group['nr_of_users']} users)")
            if group['description']:
                lst_content.append(f"  *{group['description']}*")
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

        t_user = dict()
        t_user['username'] = dict_user['username']
        t_user['name'] = dict_user['name']
        t_user['avatar'] = dict_user['avatar_template'].replace('{size}', '64')
        t_user['is_admin'] = dict_user['admin']
        t_user['is_moderator'] = dict_user['moderator']
        t_user['is_active'] = dict_user['active']
        t_user['trust_level'] = f"{trust_level[dict_user['trust_level']]} ({dict_user['trust_level']})"
        t_user['created'] = self._format_date(dict_user['created_at'])
        t_user['last_seen'] = self._format_date(dict_user['last_seen_at'])

        return t_user

    def __enumerate_users(self):
        dict_return = dict()
        dict_return["meta"] = dict()
        dict_return["content"] = list()

        lst_discourse_groups = sorted(self._get_env('DISCOURSE_GROUPS').split(','))

        dict_users = dict()

        for group in lst_discourse_groups:
            # Get all members
            results = self.__get_discourse_data(f'groups/{group}/members.json')

            dev_max_users = 3
            for user in results['members']:

                # In develop mode, we only fetch 3 users per group
                if self._get_env('STAGE') == 'dev':
                    if dev_max_users == 0:
                        break

                    #dev_max_users -= 1

                if user['id'] not in dict_users:
                    t_user = self.__get_user(user['id'])
                    t_user['groups'] = [group]

                    dict_users[user['id']] = t_user
                else:
                    dict_users[user['id']]['groups'].append(group)

        # Meta info
        dict_return["meta"] = {
            "user_count": len(dict_users),
            "user_count_active": len([user for user in dict_users.items() if user[1]['is_active'] is True]),
            "user_count_admin": len([user for user in dict_users.items() if user[1]['is_admin'] is True]),
            "user_count_moderator": len([user for user in dict_users.items() if user[1]['is_moderator'] is True]),
            "groups_scanned": ', '.join(lst_discourse_groups)
        }

        # Content
        dict_return['content'] = dict_users

        return dict_return

    def __users_to_markdown(self, dict_users):
        lst_content = list()

        lst_content.append(">[!info] General information")
        lst_content.append(f">**Users:** {dict_users['meta']['user_count']}")
        lst_content.append(f">**Active users:** {dict_users['meta']['user_count_active']}")
        lst_content.append(f">**Admins:** {dict_users['meta']['user_count_admin']}")
        lst_content.append(f">**Moderators:** {dict_users['meta']['user_count_moderator']}")
        lst_content.append(f">**Groups scanned:** {dict_users['meta']['groups_scanned']}")
        lst_content.append('')

        # Sort alphabetically on the name
        users_sorted = OrderedDict(sorted(dict_users["content"].items(), key=lambda item: item[1]["username"]))

        for _id, user in users_sorted.items():
            if 'avatar' in user:
                avatar = (f'<img src="https://{self.discourse_api_host + user["avatar"]}" '
                          f'style="width: 75px; float: left; margin-right: 10px" />')
            else:
                avatar = ''

            if user['name'] == '':
                display_name = user['username']
            else:
                display_name = user['name'] + " (" + user['username'] + ")"

            # Paste avatar image in front of name for proper alignment
            lst_content.append(avatar + "**Name:** " + display_name)

            lst_content.append(f"**Created:** {user['created']}")
            lst_content.append(f"**Last seen:** {user['last_seen']}")

            # Status
            status = "Active" if user['is_active'] else "Inactive"
            status_color = "green" if user['is_active'] else "#e94b45"
            str_status = f"<span style=\"color: {status_color}; font-weight: bold\">[{status}]</span>"

            lst_content.append(f"**Status:** {str_status}")
            lst_content.append(f"**Trust level:** {user['trust_level']}")

            # Admin
            admin = "yes" if user['is_admin'] else "no"
            admin_color = "#4c82a9" if user['is_admin'] else ""
            admin_weight = "bold" if user['is_admin'] else ""
            str_admin = f"<span style=\"color: {admin_color}; font-weight: {admin_weight}\">{admin}</span>"
            lst_content.append(f"**Admin:** {str_admin}")

            # Moderator
            moderator = "yes" if user['is_moderator'] else "no"
            mod_color = "#584a5f" if user['is_moderator'] else ""
            mod_weight = "bold" if user['is_moderator'] else ""
            str_moderator = f"<span style=\"color: {mod_color}; font-weight: {mod_weight}\">{moderator}</span>"
            lst_content.append(f"**Moderator:** {str_moderator}")

            lst_content.append(f"**Groups:** {', '.join(user['groups'])}")
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
