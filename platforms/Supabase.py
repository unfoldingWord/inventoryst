from nacl.pwhash import kdf_scryptsalsa208sha256

from platforms import Platform
from pprint import pp

# The rate limit for the Management API is 60 requests per one minute per user.
# https://supabase.com/docs/reference/api/start

class Supabase(Platform):
  def __init__(self):
    super().__init__()

    self.__config = self.load_config('supabase')
    self.__api_url = 'https://api.supabase.com/v1'
    self.__headers = [
      ['Authorization', 'Bearer ' + self.__config['pat']],
    ]

  def __enumerate_organizations(self):
    dict_return = dict()
    dict_return['meta'] = dict()
    dict_return['content'] = list()

    url_organizations = f'{self.__api_url}/organizations'
    orgs = self._get_json_from_url(url_organizations, headers=self.__headers)

    dict_return['meta']['org_count'] = len(orgs)

    field_filter = ['id', 'name']

    for org in orgs:
      dict_org = self._filter_fields(org, field_filter)

      # Get more org details: plan
      url_org = f'{self.__api_url}/organizations/{org['id']}'
      dict_org['plan'] = self._get_json_from_url(url_org, headers=self.__headers)['plan']

      # Members of the org
      dict_org['members'] = self.__enumerate_org_members(org['id'])['content']

      # Projects
      dict_org['projects'] = self.__enumerate_projects(org['id'])['content']

      dict_return['content'].append(dict_org)

    return dict_return

  def __enumerate_org_members(self, org_id):
    dict_return = dict()
    dict_return['meta'] = dict()
    dict_return['content'] = list()

    url_members = f'{self.__api_url}/organizations/{org_id}/members'
    members = self._get_json_from_url(url_members, headers=self.__headers)

    dict_return['meta']['member_count'] = len(members)
    dict_return['content'] = members

    return dict_return

  def __enumerate_projects(self, org_id):
    dict_return = dict()
    dict_return['meta'] = dict()
    dict_return['content'] = list()

    url_projects = f'{self.__api_url}/projects'
    projects = self._get_json_from_url(url_projects, headers=self.__headers)

    # Only get projects for the given organization
    dict_projects = [project for project in projects if project['organization_id'] == org_id]

    dict_return['meta']['project_count'] = len(dict_projects)

    field_filter = ['id', 'name', 'region', 'status', 'database', 'created_at']

    for project in dict_projects:
      dict_project = self._filter_fields(project, field_filter)
      dict_return['content'].append(dict_project)

    return dict_return

  def __markdown_organizations(self, dict_organizations):
    lst_content = list()

    lst_content.append(">[!info] General information")
    lst_content.append(self._item('Organizations', dict_organizations["meta"]["org_count"]))
    lst_content.append("")

    for org in dict_organizations['content']:
      lst_content.append(self._header(org['name'], 3))
      lst_content.append(self._item('Plan', org['plan']))
      lst_content.append(self._item('Members', ''))
      for member in org['members']:
        if member['user_name'] == member['email']:
          name = f'{member['user_name']}'
        else:
          name = f'{member['user_name']} ({member['email']})'

        lst_content.append(f'- {self._item('Name', name)}')
        lst_content.append('  ' + self._item('Role', member['role_name']))

        # MFA
        mfa_color = 'green' if member['mfa_enabled'] else 'red'
        mfa_title = 'Yes' if member['mfa_enabled'] else 'No'
        lst_content.append('  ' + self._item('MFA', self._highlight(mfa_title, 'white', border_color='white', background=mfa_color)))

      if org['projects']:
        lst_content.append('')
        lst_content.append(self._item('Projects', ''))
        for project in org['projects']:
          lst_content.append(f'- {self._item('Name', project['name'])}')
          lst_content.append('  ' + self._item('ID', project['id']))
          lst_content.append('  ' + self._item('Created', self._format_date(project['created_at'])))
          lst_content.append('  ' + self._item('Region', project['region']))
          lst_content.append('  ' + self._item('DB host', project['database']['host']))
          lst_content.append('  ' + self._item('DB version', project['database']['version']))
          lst_content.append('  ' + self._item('DB PostgreSQL engine', project['database']['postgres_engine']))

    page = 'supabase.md'
    return {page: lst_content}

  def _build_content(self):
    md_main = dict()

    organizations= self.__enumerate_organizations()
    md_main.update(self.__markdown_organizations(organizations))

    return md_main
