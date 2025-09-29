from .Platform import Platform
from dateutil import parser
from datetime import datetime
from pprint import pp


class Netlify(Platform):
    def __init__(self):
        super().__init__()

        self.__config = self.load_config('netlify')
        self.__api_url = self.__config['api_url']
        self.__api_key = self.__config['api_key']
        self.__team = self.__config['team']

        self.__headers = [['Authorization', 'Bearer ' + self.__api_key]]


    def __enumerate_users(self):
        dict_users = dict()
        dict_users["meta"] = dict()
        dict_users["content"] = list()

        url_users = self.__api_url + f'/{self.__team}/members'
        lst_users = self._get_json_from_url(url=url_users, headers=self.__headers)

        dict_users["meta"]["user_count"] = len(lst_users)

        field_filter = ['full_name', 'email', 'mfa_enabled', 'role', 'site_access', 'pending', 'last_activity_date']

        for user in lst_users:
            dict_user = self._filter_fields(user, field_filter)

            # Fix empty name
            dict_user['name'] = user['full_name'] if user['full_name'] else user['email']

            dict_users['content'].append(dict_user)

        # Sort users alphabetically and return
        dict_users['content'] = sorted(dict_users['content'], key=lambda item: item["name"].lower())
        return dict_users

    def __markdown_users(self, inventory):
        lst_content = list()

        lst_content.append(">[!info] General information")
        lst_content.append(self._item('Overview', self._link(f'https://app.netlify.com/teams/{self.__team}/members', 'Members')))
        lst_content.append(self._item('Number of members', inventory["meta"]["user_count"]))
        lst_content.append("")

        for user in inventory["content"]:
            # Label: 2FA
            if user['mfa_enabled'] is False:
                label_2fa = self._highlight('No 2FA', 'orange', border_color='orange')
            else:
                label_2fa = self._highlight('2FA', 'green', border_color='green')

            # Label: activity
            if user['last_activity_date']:
                # Status: Mark inactive when not logged in for a month
                inactive_day_limit = self.__config['user_inactive_days']
                date_last_active = parser.parse(user['last_activity_date'])
                delta = datetime.today() - date_last_active

                status = "Active" if delta.days < inactive_day_limit else "Inactive"
                status_color = "green" if delta.days < inactive_day_limit else "orange"

                label_active = self._highlight(f'{status}', color=status_color, border_color=status_color)
            else:
                label_active = self._highlight('Unknown', 'orange', border_color='orange')

            # Name and email
            lst_content.append(self._header(f'{user['name']} {label_2fa} {label_active}', 3))
            lst_content.append(self._item('Email', user['email']))

            # Pending
            pending = "Yes" if user['pending'] is True else "No"
            lst_content.append(self._item('Pending', pending))

            # Last activity date
            last_active_date = self._format_date(user['last_activity_date']) if user['last_activity_date'] else 'Unknown'
            lst_content.append(self._item('Last active', last_active_date))

            lst_content.append(self._item('Role', user['role']))
            lst_content.append(self._item('Site access', user['site_access']))
            lst_content.append("")

        file = "netlify/members.md"
        return {file: lst_content}

    def __get_env_vars_for_site(self, site_id):
        url_env_vars = self.__api_url + f'/accounts/{self.__team}/env?site_id={site_id}'
        lst_env_vars = self._get_json_from_url(url=url_env_vars, headers=self.__headers)

        lst_return = list()
        if len(lst_env_vars) > 0:
            lst_return = [item['key'] for item in lst_env_vars]

        return sorted(lst_return)

    def __get_deploys_for_site(self, site_id):
        # Get last 5 production deploys
        last_deploys = self.__config['last_deploys']
        url_deploys = self.__api_url + f'/sites/{site_id}/deploys?production=true&per_page={last_deploys}'
        lst_deploys = self._get_json_from_url(url=url_deploys, headers=self.__headers)

        lst_deploys = sorted(lst_deploys, key=lambda item: item["created_at"], reverse=True)

        field_filter = ['created_at', 'id', 'state', 'error_message']

        lst_return = list()
        for deploy in lst_deploys:
            lst_return.append(self._filter_fields(deploy, field_filter))

        return lst_return

    def __get_ssl_cert(self, site_id):
        url_cert = self.__api_url + f'/sites/{site_id}/ssl'
        dict_cert = self._get_json_from_url(url=url_cert, headers=self.__headers)

        return dict_cert

    def __enumerate_sites(self):
        dict_sites = dict()
        dict_sites["meta"] = dict()
        dict_sites["content"] = list()

        url_sites = self.__api_url + f'/{self.__team}/sites'
        lst_sites = self._get_json_from_url(url=url_sites, headers=self.__headers)

        dict_sites["meta"]["site_count"] = len(lst_sites)

        field_filter = ['created_at', 'default_domain', 'site_id', 'name', 'ssl_url', 'disabled']
        for site in lst_sites:

            dict_site = self._filter_fields(site, field_filter)

            dict_site['created_at'] = self._format_date(dict_site['created_at'])

            if len(site['build_settings']) > 0:
                dict_site['repository'] = site['build_settings']['repo_url']
                dict_site['updated'] = self._format_date(site['build_settings']['updated_at'])

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

    def __markdown_sites(self, inventory):

        lst_content = list()

        lst_content.append(">[!info] General information")
        lst_content.append(self._item('Overview', self._link(f'https://app.netlify.com/teams/{self.__team}/sites', 'Sites')))
        lst_content.append(self._item('Number of sites', inventory["meta"]["site_count"]))
        lst_content.append("")

        # Sort alphabetically on the name
        sites_sorted = sorted(inventory["content"], key=lambda item: item["name"])

        for site in sites_sorted:

            label_disabled = self._highlight('Disabled', 'gray', border_color='gray') if site['disabled'] else ''

            site_title = self._link(f'https://app.netlify.com/sites/{site['name']}/overview', site['name'])
            lst_content.append(self._header(f'{site_title} {label_disabled}'))
            lst_content.append(self._item('URL', site['ssl_url']))
            lst_content.append(self._item('Netlify domain', site['default_domain']))
            lst_content.append(self._item('ID', f"`{site['site_id']}`"))
            lst_content.append(self._item('Created', site['created_at']))
            if 'updated' in site:
                lst_content.append(self._item('Updated', site['updated']))

            if 'repository' in site:
                lst_content.append(self._item('Repository', site['repository']))

            # Environment variables
            if site["env_vars"]:
                lst_content.append(self._item('Env vars', site['env_vars']))
            else:
                lst_content.append(self._item('Env vars', self._highlight('none', 'grey')))

            # Deploys
            if "deploys" in site:
                lst_content.append(f"**Production deploys:**")

                for deploy in site['deploys']:
                    if deploy['state'] == 'ready':
                        state = self._highlight('Published', 'green', border_color='green')
                    elif deploy['state'] == 'error':
                        if deploy['error_message'] == 'Canceled build':
                            state = self._highlight('Canceled', 'grey', border_color='grey')
                        else:
                            state = self._highlight('Error', 'red', border_color='red')
                    else:
                        state = self._highlight(f'{deploy['state']}', 'grey', border_color='grey')

                    str_deploy_date = self._format_date(deploy['created_at'])
                    #str_deploy_date = parser.parse(deploy['created_at']).strftime("%b %-d, %Y, at %-I:%M %p")

                    deploy_url = f"https://app.netlify.com/sites/{site['name']}/deploys/{deploy['id']}"
                    deploy_link = self._link(deploy_url, str_deploy_date)

                    lst_content.append(f"  * {deploy_link} {state}")
                    #lst_content.append(f"  * [{str_deploy_date}]({deploy_url}) {state}")

            # SSL
            if "tls_cert" in site:
                lst_content.append("**TLS Certificate:** ")

                #str_created_date = parser.parse(site['tls_cert']['created_at']).strftime("%b %-d, %Y at %-I:%M %p")
                str_created_date = self._format_date(site['tls_cert']['created_at'])
                lst_content.append(f"  * **Created:** {str_created_date}")
                #str_updated_date = parser.parse(site['tls_cert']['updated_at']).strftime("%b %-d, %Y at %-I:%M %p")
                str_updated_date = self._format_date(site['tls_cert']['updated_at'])
                lst_content.append(f"  * **Updated:** {str_updated_date}")
                #str_expires_date = parser.parse(site['tls_cert']['expires_at']).strftime("%b %-d, %Y at %-I:%M %p")
                str_expires_date = self._format_date(site['tls_cert']['expires_at'])
                lst_content.append(f"  * **Expires:** {str_expires_date}")

            lst_content.append("")

        file = "netlify/sites.md"
        return {file: lst_content}

    def _build_content(self):
        md_main = dict()

        # sites
        inventory = self.__enumerate_sites()
        md_main.update(self.__markdown_sites(inventory))

        # users
        inventory = self.__enumerate_users()
        md_main.update(self.__markdown_users(inventory))

        return md_main
