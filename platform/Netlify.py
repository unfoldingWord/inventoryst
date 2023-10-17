from .Platform import Platform
from pprint import pprint


class Netlify(Platform):
    def __init__(self):
        super().__init__()
        self.api_url = 'https://api.netlify.com/api/v1'
        self.api_key = self._get_env('NETLIFY_API_KEY')
        self.team = self._get_env('NETLIFY_TEAM')

    def __enumerate_users(self):
        dict_users = dict()
        dict_users["meta"] = dict()
        dict_users["content"] = list()

        url_users = self.api_url + f'/{self.team}/members'
        lst_users = self._get_json_from_url(url=url_users, authorization='Bearer ' + self.api_key)

        dict_users["meta"]["user_count"] = len(lst_users)

        for user in lst_users:
            dict_user = dict()
            if user["full_name"]:
                dict_user["name"] = user["full_name"]
            else:
                dict_user["name"] = user["email"]
            dict_user["email"] = user["email"]
            dict_user["2fa"] = user["mfa_enabled"]
            dict_user["role"] = user["role"]
            dict_user["site_access"] = user["site_access"]
            dict_user["pending"] = user["pending"]

            dict_users["content"].append(dict_user)

        return dict_users

    def __users_to_markdown(self, inventory):
        lst_content = list()

        lst_content.append(">[!info] General information")
        lst_content.append(f">**Overview:** [Members](https://app.netlify.com/teams/{self.team}/members)")
        lst_content.append("**Number of members:** " + str(inventory["meta"]["user_count"]))
        lst_content.append("")

        for user in inventory["content"]:
            lst_content.append(f"### {user['name']}")
            lst_content.append(f"**Email:** {user['email']}")

            # Status
            status = "Active" if user['pending'] is False else "Pending"
            status_color = "green" if user['pending'] is False else "orange"
            str_status = f"<span style=\"color: {status_color}; font-weight: bold\">[{status}]</span>"

            # 2FA
            str_2fa = ""
            if user["2fa"] is False:
                str_2fa = "<span style=\"color: orange; font-weight: bold\">[No 2FA]</span>"

            lst_content.append(f"**Status:** {str_status} {str_2fa}")

            lst_content.append(f"**Role:** {user['role']}")
            lst_content.append(f"**Site access:** {user['site_access']}")
            lst_content.append("")

        file = "netlify/members.md"
        return {file: lst_content}

    def __enumerate_sites(self):
        dict_sites = dict()
        dict_sites["meta"] = dict()
        dict_sites["content"] = list()

        url_sites = self.api_url + f'/{self.team}/sites'
        lst_sites = self._get_json_from_url(url=url_sites, authorization='Bearer ' + self.api_key)

        dict_sites["meta"]["site_count"] = len(lst_sites)

        for site in lst_sites:

            dict_site = dict()
            dict_site['created'] = site['created_at']
            dict_site['domain'] = site['default_domain']
            dict_site['id'] = site['site_id']
            dict_site['name'] = site['name']
            dict_site['url'] = site['ssl_url']
            if len(site['build_settings']) > 0:
                dict_site['repository'] = site['build_settings']['repo_url']
                dict_site['updated'] = site['build_settings']['updated_at']

            dict_sites["content"].append(dict_site)

        return dict_sites

    def __sites_to_markdown(self, inventory):

        lst_content = list()

        lst_content.append(">[!info] General information")
        lst_content.append(f">**Overview:** [Sites](https://app.netlify.com/teams/{self.team}/sites)")
        lst_content.append("**Number of sites:** " + str(inventory["meta"]["site_count"]))
        lst_content.append("")

        # Sort alphabetically on the name
        sites_sorted = sorted(inventory["content"], key=lambda item: item["name"])

        for site in sites_sorted:

            lst_content.append(f"### {site['name']}")
            lst_content.append(f"**Domain:** {site['domain']}")
            lst_content.append(f"**ID:** {site['id']}")
            if 'repository' in site:
                lst_content.append(f"**Repository:** {site['repository']}")
                lst_content.append(f"**Updated:** {site['updated']}")
            lst_content.append(f"**URL:** {site['url']}")
            lst_content.append("")

        file = "netlify/sites.md"
        return {file: lst_content}

    def _build_content(self):
        md_main = dict()

        # sites
        inventory = self.__enumerate_sites()
        md_main.update(self.__sites_to_markdown(inventory))

        # users
        inventory = self.__enumerate_users()
        md_main.update(self.__users_to_markdown(inventory))

        return md_main

