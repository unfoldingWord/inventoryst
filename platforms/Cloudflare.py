from github.Consts import mediaTypeReactionsPreview

from .Platform import Platform
from cloudflare import Cloudflare as CF
from pprint import pp
import json


class Cloudflare(Platform):
  def __init__(self):
    super().__init__()

    # Loading configuration
    self.__config = self.load_config('cloudflare')

    self.__cf_agent = CF(api_token=self.__config['api_token'])
    self._inc_api_call()
    self.__cf_account_id = self.__config['account_id']

  def __enumerate_members(self):
    dict_return = dict()
    dict_return['meta'] = dict()
    dict_return['content'] = list()

    members = json.loads(self.__cf_agent.accounts.members.list(account_id=self.__cf_account_id).model_dump_json())['result']
    self._inc_api_call()

    dict_return['meta']['member_count'] = len(members)

    user_field_filter = ['email', 'first_name', 'last_name', 'two_factor_authentication_enabled']
    role_field_filter = ['name', 'description']
    for member in members:

      dict_member = self._filter_fields(member['user'], user_field_filter)
      dict_member['status'] = member['status']

      dict_member['roles'] = list()
      for role in member['roles']:
        dict_member['roles'].append(self._filter_fields(role, role_field_filter))

      dict_return['content'].append(dict_member)

    return dict_return

  def __enumerate_page_projects(self):
    dict_return = dict()
    dict_return['meta'] = dict()
    dict_return['content'] = list()

    projects =  json.loads(self.__cf_agent.pages.projects.list(account_id=self.__cf_account_id).model_dump_json())['result']
    self._inc_api_call()

    dict_return['meta']['project_count'] = len(projects)

    project_field_filter = ['id', 'created_on', 'name', 'subdomain', 'domains']
    deployment_field_filter = ['modified_on', 'url', 'env_vars', 'source']

    for project in projects:
      dict_project = self._filter_fields(project, project_field_filter)

      if project['latest_deployment']:
        dict_project['latest_deployment'] = self._filter_fields(project['latest_deployment'], deployment_field_filter)
        dict_project['latest_deployment']['result'] = project['latest_deployment']['latest_stage']['status']

      dict_return['content'].append(dict_project)

    return dict_return

  def __enumerate_r2_buckets(self):
    dict_return = dict()
    dict_return['meta'] = dict()
    dict_return['content'] = list()

    buckets = json.loads(self.__cf_agent.r2.buckets.list(account_id=self.__cf_account_id).model_dump_json())['buckets']
    self._inc_api_call()

    dict_return['meta']['bucket_count'] = len(buckets)

    # Bucket metrics
    # metrics = json.loads(self.__cf_agent.r2.buckets.metrics.list(account_id=self.__cf_account_id).model_dump_json())
    # pp(metrics)
    # exit()

    for item in buckets:
      bucket = json.loads(self.__cf_agent.r2.buckets.get(account_id=self.__cf_account_id, bucket_name=item['name']).model_dump_json())
      self._inc_api_call()

      dict_return['content'].append(bucket)

    return dict_return

  def __code_to_location(self, code):
    dict_map = {
      'APAC': 'Asia-Pacific',
      'EEUR': 'Eastern Europe',
      'ENAM': 'Eastern North America',
      'OC': 'Oceania',
      'WEUR': 'Western Europe',
      'WNAM': 'Western North America',
    }

    return dict_map[code]

  def __markdown_r2_buckets(self, buckets):
    lst_content = list()

    lst_content.append(">[!info] General information")
    lst_content.append(self._item('Buckets', buckets['meta']['bucket_count']))
    lst_content.append('')

    for bucket in buckets['content']:
      lst_content.append(f'- `{bucket['name']}`')
      lst_content.append(self._item('Created', self._format_date(bucket['creation_date'])))
      lst_content.append(self._item('Storage class', bucket['storage_class']))
      lst_content.append(self._item('Location', f'{self.__code_to_location(bucket['location'])} ({bucket['location']})'))
      lst_content.append(self._item('Jurisdiction', bucket['jurisdiction']))

      # TODO, we would like to add bucket metrics (objectCount, payloadSize) to this list.

    page = 'cloudflare/r2.md'
    return {page: lst_content}

  def __markdown_page_projects(self, projects):
    lst_content = list()

    lst_content.append(">[!info] General information")
    lst_content.append(self._item('Projects', projects['meta']['project_count']))
    lst_content.append('')

    for project in projects['content']:
      lst_content.append(self._header(project['name'], 3))
      lst_content.append(self._item('ID', f'`{project['id']}`'))
      lst_content.append(self._item('Created', self._format_date(project['created_on'])))
      lst_content.append(self._item('Subdomain', project['subdomain']))
      lst_content.append(self._item('Domains', ', '.join(project['domains'])))

      # Env vars
      env_vars = '`, `'.join(list(project['latest_deployment']['env_vars'].keys()))
      lst_content.append(self._item('ENV vars', f'`{env_vars}`'))

      # Latest deployment
      last_deployed = self._format_date(project['latest_deployment']['modified_on'])
      deploy_status = project['latest_deployment']['result']
      lst_content.append(self._item('Latest deployment', f'{last_deployed} ({deploy_status})'))

      # Deployment source
      deploy_source = project['latest_deployment']['source']
      if deploy_source['type'] == 'github':
        source_url = (f'https://github.com/{deploy_source['config']['owner']}/{deploy_source['config']['repo_name']} '
                      f'(`{deploy_source['config']['production_branch']}`)')
      else:
        source_url = ''
      lst_content.append(self._item('Deployed from', source_url))

    page = 'cloudflare/pages.md'
    return {page: lst_content}


  def __markdown_members(self, members):
    lst_content = list()

    lst_content.append(">[!info] General information")
    lst_content.append(self._item('Members', members['meta']['member_count']))
    lst_content.append('')

    for member in members['content']:
      label_status = ''
      if member['status'] == 'pending':
        label_status = self._highlight('Pending', color='white', background='#73cee6', border_color='white')

      if member['first_name'] and member['last_name']:
        name = f'{member['first_name']} {member['last_name']} ({member['email']})'
      else:
        name = member['email']
      lst_content.append(f'{self._header(name, 3)} {label_status}')

      # MFA
      if member['two_factor_authentication_enabled'] is True:
        mfa_enabled = 'Enabled'
      else:
        mfa_enabled = self._highlight('Disabled', color='white', background='red', border_color='white')

      lst_content.append(self._item('MFA', mfa_enabled))

      # Roles
      lst_content.append(self._item('Roles', ''))
      for role in member['roles']:
        lst_content.append(f'- {role['name']}')
        lst_content.append(self._note(role['description']))


    page = 'cloudflare/members.md'
    return {page: lst_content}

  def _build_content(self):
    md_main = dict()

    # members = self.__enumerate_members()
    # md_main.update(self.__markdown_members(members))
    #
    # page_projects = self.__enumerate_page_projects()
    # md_main.update(self.__markdown_page_projects(page_projects))

    r2_buckets = self.__enumerate_r2_buckets()
    md_main.update(self.__markdown_r2_buckets(r2_buckets))

    return md_main