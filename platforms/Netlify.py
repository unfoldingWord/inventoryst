from .Platform import Platform
from dateutil import parser
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
        lst_users = self._get_json_from_url(url=url_users, headers=[['Authorization', 'Bearer ' + self.api_key]])

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

        # Sort users alphabetically and return
        dict_users['content'] = sorted(dict_users["content"], key=lambda item: item["name"].lower())
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

    def __get_env_vars_for_site(self, site_id):
        url_env_vars = self.api_url + f'/accounts/{self.team}/env?site_id={site_id}'
        lst_env_vars = self._get_json_from_url(url=url_env_vars, headers=[['Authorization', 'Bearer ' + self.api_key]])

        lst_return = list()
        if len(lst_env_vars) > 0:
            for item in lst_env_vars:
                lst_return.append(item["key"])

        return sorted(lst_return)

    def __get_deploys_for_site(self, site_id):
        # Get last 5 production deploys
        url_deploys = self.api_url + f'/sites/{site_id}/deploys?production=true&per_page=5'
        lst_deploys = self._get_json_from_url(url=url_deploys, headers=[['Authorization', 'Bearer ' + self.api_key]])

        lst_deploys = sorted(lst_deploys, key=lambda item: item["created_at"], reverse=True)

        lst_return = list()
        for deploy in lst_deploys:
            lst_return.append({
                'created_at': deploy['created_at'],
                'id': deploy['id'],
                'state': deploy['state'],
                'error_message': deploy['error_message']
            })

        return lst_return

    def __get_ssl_cert(self, site_id):
        url_cert = self.api_url + f'/sites/{site_id}/ssl'
        dict_cert = self._get_json_from_url(url=url_cert, headers=[['Authorization', 'Bearer ' + self.api_key]])

        return dict_cert

    def __enumerate_sites(self):
        dict_sites = dict()
        dict_sites["meta"] = dict()
        dict_sites["content"] = list()

        url_sites = self.api_url + f'/{self.team}/sites'
        lst_sites = self._get_json_from_url(url=url_sites, headers=[['Authorization', 'Bearer ' + self.api_key]])

        dict_sites["meta"]["site_count"] = len(lst_sites)

        for site in lst_sites:
            # pprint(site)
            # exit()

            dict_site = dict()
            dict_site['created'] = site['created_at']
            dict_site['domain'] = site['default_domain']
            dict_site['id'] = site['site_id']
            dict_site['name'] = site['name']
            dict_site['url'] = site['ssl_url']
            if len(site['build_settings']) > 0:
                dict_site['repository'] = site['build_settings']['repo_url']

                str_date = parser.parse(site['build_settings']['updated_at']).strftime("%a, %b %-d, %Y, %-I:%M %p")
                dict_site['updated'] = str_date

            # Environment variables
            dict_site['env_vars'] = ", ".join(self.__get_env_vars_for_site(site['site_id']))

            # Deploys
            lst_deploys = self.__get_deploys_for_site(site['site_id'])
            if len(lst_deploys) > 0:
                dict_site['deploys'] = lst_deploys

            # TLS certificate
            dict_cert = self.__get_ssl_cert(site['site_id'])
            if dict_cert:
                dict_site['tls_cert'] = dict_cert

            # Wrap up
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

            lst_content.append(f"### [{site['name']}](https://app.netlify.com/sites/{site['name']}/overview)")
            lst_content.append(f"**URL:** {site['url']}")
            lst_content.append(f"**Netlify domain:** {site['domain']}")
            if 'repository' in site:
                lst_content.append(f"**Repository:** {site['repository']}")
                lst_content.append(f"**Updated:** {site['updated']}")
            lst_content.append(f"**ID:** {site['id']}")

            # Environment variables
            if site["env_vars"]:
                lst_content.append(f"**Env vars:** {site['env_vars']}")
            else:
                lst_content.append(f"**Env vars:** <span style=\"color: grey\">none</span>")

            # Deploys
            if "deploys" in site:
                lst_content.append(f"**Production deploys:**")

                for deploy in site['deploys']:
                    if deploy['state'] == 'ready':
                        state = "<span style=\"font-weight: bold; color: green\">[ Published ]</span>"
                    elif deploy['state'] == 'error':
                        if deploy['error_message'] == 'Canceled build':
                            state = f"<span style=\"font-weight: bold; color: grey\">[ Canceled ]</span>"
                        else:
                            state = f"<span style=\"font-weight: bold; color: red\">[ Error ]</span>"
                    else:
                        state = f"<span style=\"font-weight: bold; color: grey\">[ {deploy['state']} ]</span>"

                    str_deploy_date = parser.parse(deploy['created_at']).strftime("%b %-d, %Y, at %-I:%M %p")

                    deploy_url = f"https://app.netlify.com/sites/{site['name']}/deploys/{deploy['id']}"

                    lst_content.append(f"  * [{str_deploy_date}]({deploy_url}) {state}")

            # SSL
            if "tls_cert" in site:
                lst_content.append("**TLS Certificate:** ")

                str_created_date = parser.parse(site['tls_cert']['created_at']).strftime("%b %-d, %Y at %-I:%M %p")
                lst_content.append(f"  * **Created:** {str_created_date}")
                str_updated_date = parser.parse(site['tls_cert']['updated_at']).strftime("%b %-d, %Y at %-I:%M %p")
                lst_content.append(f"  * **Updated:** {str_updated_date}")
                str_expires_date = parser.parse(site['tls_cert']['expires_at']).strftime("%b %-d, %Y at %-I:%M %p")
                lst_content.append(f"  * **Expires:** {str_expires_date}")

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
