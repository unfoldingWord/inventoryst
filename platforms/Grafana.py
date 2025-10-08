from datetime import datetime, timezone
from .Platform import Platform
from pprint import pp
from dateutil import parser

class Grafana(Platform):
  def __init__(self):
    super().__init__()

    # Load config
    self.__config = self.load_config('grafana')

    self.__api_host = f'{self.__config['host']}/api'
    self.__new_api_host = f'{self.__config['host']}/apis'
    self.__headers = [
      ['Authorization', 'Bearer ' + self.__config['token']],
    ]
    self.__generic_folder_uid = 'gen-001'

  def __enumerate_users(self):
    dict_return = dict()
    dict_return["meta"] = dict()
    dict_return["content"] = list()

    url_users = f'{self.__api_host}/org/users'

    users = self._get_json_from_url(url_users, headers=self.__headers)

    dict_return['meta']['user_count'] = len(users)

    field_filter = ['email', 'name', 'login', 'avatarUrl', 'role', 'lastSeenAt', 'lastSeenAtAge', 'isDisabled', 'authLabels']

    inactive_count = 0
    for user in users:
      dict_user = self._filter_fields(user, field_filter)

      # Activity
      dict_user['inactive'] = False
      inactive_days = (datetime.now(timezone.utc) - parser.parse(user['lastSeenAt'])).days
      if inactive_days > self.__config['user']['inactive_days']:
        dict_user['inactive'] = True
        inactive_count += 1

      dict_return['content'].append(dict_user)

    dict_return['meta']['inactive_user_count'] = inactive_count

    return dict_return

  def __enumerate_teams(self):
    dict_return = dict()
    dict_return["meta"] = dict()
    dict_return["content"] = list()

    url_teams = f'{self.__api_host}/teams/search'
    teams = self._get_json_from_url(url_teams, headers=self.__headers)['teams']

    dict_return['meta']['team_count'] = len(teams)

    field_filter = ['name', 'avatarUrl', 'memberCount']
    for team in teams:
      dict_team = self._filter_fields(team, field_filter)

      # Get team members
      url_members = f'{self.__api_host}/teams/{team['id']}/members'
      members = self._get_json_from_url(url_members, headers=self.__headers)

      dict_team['members'] = [member['name'] for member in members]

      dict_return['content'].append(dict_team)

    return dict_return

  def __get_folders(self):
    url_folders = f'{self.__api_host}/folders'
    folders = self._get_json_from_url(url_folders, headers=self.__headers)

    folder_field_filter = ['id', 'uid', 'title', 'url', 'created', 'updated']

    dict_folders = dict()
    for folder in folders:
      # Get specific folder data
      url_this_folder = f'{self.__api_host}/folders/{folder['uid']}'
      this_folder = self._get_json_from_url(url_this_folder, headers=self.__headers)

      dict_folder = self._filter_fields(this_folder, folder_field_filter)
      dict_folder['dashboards'] = list()

      dict_folders[folder['uid']] = dict_folder

    # Add General folder manually
    # The General folder is a 'virtual' folder that collects all orphan dashboards
    gen_folder_uid = self.__generic_folder_uid
    dict_folders[gen_folder_uid] = {
      'id': 0,
      'uid': gen_folder_uid,
      'title': 'General',
      'url': '',
      'dashboards': list()
    }

    return dict_folders

  def __enumerate_dashboards(self):
    dict_return = dict()
    dict_return["meta"] = dict()
    dict_return["content"] = list()

    # Get the dashboards
    url_dashboards = f'{self.__api_host}/search?type=dash-db'
    dashboards = self._get_json_from_url(url_dashboards, headers=self.__headers)

    # Total number of dashboards
    dict_return['meta']['dashboard_count'] = len(dashboards)

    dashboard_field_filter = ['id', 'uid', 'title', 'url', 'folderId']

    dict_folders = self.__get_folders()
    for dashboard in dashboards:

      # Basic stuff
      dict_dashboard = self._filter_fields(dashboard, dashboard_field_filter)

      # Add dashboard to the correct folder
      if 'folderUid' in dashboard:
        folder_uid = dashboard['folderUid']
      else:
        # Dashboard has no folder, this is the Generic folder
        folder_uid = self.__generic_folder_uid

      dict_folders[folder_uid]['dashboards'].append(dict_dashboard)

    # Total number of folders
    dict_return['meta']['folder_count'] = len(dict_folders)

    # Clean up
    for folder in dict_folders:
      dict_return['content'].append(dict_folders[folder])

    return dict_return

  def __markdown_dashboards(self, dashboards):
    lst_content = list()

    # Info block
    lst_content.append(">[!info] General information")
    lst_content.append(self._item('Number of folders', dashboards['meta']['folder_count']))
    lst_content.append(self._item('Number of dashboards', dashboards['meta']['dashboard_count']))
    lst_content.append("")

    # Dashboards are organized by folder
    # I'd like to sort by folder name (later)
    for folder in dashboards['content']:

      # Folder stuff
      lst_content.append(self._header(f'{folder['title']} ({len(folder['dashboards'])})', 3))
      lst_content.append(self._item('URL', f'{self.__config['host']}{folder['url']}'))
      if 'updated' in folder:
        lst_content.append(self._item('Last updated', self._format_date(folder['updated'])))
      lst_content.append('')

      # Dashboards
      for dashboard in folder['dashboards']:
        dashboard = self._link(f'{self.__config['host']}{dashboard['url']}', dashboard['title'])
        lst_content.append(f'- {dashboard}')

    page = 'grafana/dashboards.md'
    return {page: lst_content}

  def __markdown_teams_users(self, teams, users):
    lst_content = list()

    # Info block
    lst_content.append(">[!info] General information")
    lst_content.append(self._item('Teams', teams['meta']['team_count']))
    lst_content.append(self._item('Users', users['meta']['user_count']))
    lst_content.append(self._item('Inactive users', users['meta']['inactive_user_count']))
    lst_content.append("")

    # Teams
    lst_content.append(self._header('Teams'))
    for team in teams['content']:
      avatar = self._avatar(f'{self.__config['host']}{team['avatarUrl']}')

      lst_content.append(avatar + self._item('Name', team['name']))
      lst_content.append(self._item('Member count', team['memberCount']))

      # Members
      members = ', '.join(team['members']) if team['members'] else 'none'
      lst_content.append(self._item('Members', members))
      lst_content.append('')

    # Users
    lst_content.append(self._header('Users'))
    for user in users['content']:

      # Avatar
      avatar = self._avatar(f'{self.__config['host']}{user['avatarUrl']}')

      # Labels
      lst_labels = list()
      # - Disabled?
      lst_labels.append(self._highlight('Disabled', 'gray', border_color='gray') if user['isDisabled'] else '')
      # - Inactive?
      if user['inactive'] is True:
        lst_labels.append(self._highlight('Inactive', 'orange', border_color='orange'))

      name = user['name'] if user['name'] else user['login']
      lst_content.append(avatar + self._item('Name', name) + ' '.join(lst_labels))
      lst_content.append(self._item('Email', user['email']))
      lst_content.append(self._item('Role', user['role']))
      lst_content.append(self._item('Last seen', f'{self._format_date(user['lastSeenAt'])} ({user['lastSeenAtAge']} ago)'))

      # Authentication method
      auth_methods = 'password' if user['authLabels'] is None else ', '.join(user['authLabels'])
      lst_content.append(self._item('Auth method', auth_methods))
      lst_content.append('')

    page = 'grafana/teams_users.md'
    return {page: lst_content}

  def _build_content(self):
    md_main = dict()

    teams = self.__enumerate_teams()
    users = self.__enumerate_users()
    md_main.update(self.__markdown_teams_users(teams, users))

    dashboards = self.__enumerate_dashboards()
    md_main.update(self.__markdown_dashboards(dashboards))

    return md_main