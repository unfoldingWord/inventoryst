from .Platform import Platform

class DockerHub(Platform):

  def __init__(self):
    super().__init__()

    self.__api_url = 'https://hub.docker.com/v2'
    self.__org_name = self._get_env('DOCKER_ORG')
    api_access_token = self.__request_access_token()
    self.__headers = [
      ['Authorization', 'Bearer ' + api_access_token],
    ]

  def __request_access_token(self):
    org_access_token = self._get_env('DOCKER_OAT')
    url = f"{self.__api_url}/auth/token"
    data = {
      'identifier': self.__org_name,
      'secret': org_access_token
    }

    # Get my access token
    token_data = self._get_json_from_url(url, data=data)
    if 'access_token' in token_data:
      return token_data['access_token']
    else:
      self._logger.fatal(f"Can not request access token: {token_data}")
      raise Exception(f'Authentication failed: {token_data}')

  def __enumerate_repositories(self):
    dict_repos = dict()
    dict_repos["meta"] = dict()
    dict_repos["content"] = list()

    url = f"{self.__api_url}/namespaces/{self.__org_name}/repositories?page_size=100&ordering=last_updated"
    repo_data = self._get_json_from_url(url)

    if 'results' in repo_data:

      dict_repos['meta']['repo_count'] = repo_data['count']

      lst_repo_field_filter = ['name', 'status_description', 'description', 'is_private', 'pull_count',
                               'last_updated', 'date_registered', 'categories', 'storage_size']
      for repository in repo_data['results']:
        dict_repo = self._field_filter(repository, lst_repo_field_filter)

        # Supplement with tag data
        tag_data = self.__enumerate_repository_tags(repository['name'])
        if len(tag_data['content']):
          dict_repo['tags'] = tag_data

        dict_repos['content'].append(dict_repo)

    return dict_repos

  def __enumerate_repository_tags(self, repository):
    dict_tags = dict()
    dict_tags['meta'] = dict()
    dict_tags['content'] = list()

    url = f"{self.__api_url}/namespaces/{self.__org_name}/repositories/{repository}/tags"

    tag_data = self._get_json_from_url(url)

    if 'results' in tag_data:
      dict_tags['meta']['tag_count'] = tag_data['count']

      lst_tag_field_filter = ['name', 'last_updated', 'full_size', 'tag_last_pushed', 'digest']
      for tag in tag_data['results']:
        dict_tag = self._field_filter(tag, lst_tag_field_filter)
        dict_tags['content'].append(dict_tag)

    return dict_tags

  def __enumerate_members(self):
    url = f"{self.__api_url}/orgs/{self.__org_name}/members"

    user_data = self._get_json_from_url(url, headers=self.__headers)
    return user_data

  def __enumerate_groups(self):
    url = f"{self.__api_url}/orgs/{self.__org_name}/groups"

    group_data = self._get_json_from_url(url, headers=self.__headers)
    return group_data

  def __enumerate_group_members(self, group_name):
    url = f"{self.__api_url}/orgs/{self.__org_name}/groups/{group_name}/members"

    member_data = self._get_json_from_url(url, headers=self.__headers)
    return member_data

  def __enumerate_teams_users(self):
    dict_users = dict()
    dict_users["meta"] = dict()
    dict_users["content"] = dict()
    dict_users["content"]['users'] = list()
    dict_users["content"]['teams'] = list()

    # Get the users
    users = self.__enumerate_members()
    list_user_field_filter = ['username', 'email', 'full_name', 'role', 'type', 'date_joined', 'groups']

    if 'results' in users:
      dict_users['meta']['user_count'] = users['count']
      for user in users['results']:
        dict_user = self._field_filter(user, list_user_field_filter)
        dict_users['content']['users'].append(dict_user)

    # Get the teams
    teams = self.__enumerate_groups()
    list_team_field_filter = ['member_count', 'name']

    if 'results' in teams:
      dict_users['meta']['team_count'] = teams['count']
      for team in teams['results']:
        dict_team = self._field_filter(team, list_team_field_filter)

        members = self.__enumerate_group_members(dict_team['name'])
        if 'results' in members:
          dict_team['members'] = [user['username'] for user in members['results']]
          dict_users['content']['teams'].append(dict_team)

    return dict_users

  def __repositories_to_markdown(self, dict_repositories):
    lst_content = list()

    # Info block
    lst_content.append(">[!info] General information")
    lst_content.append(self._item('Number of repositories', dict_repositories['meta']['repo_count']))
    lst_content.append("")

    # Repositories
    for repo in dict_repositories['content']:
      lst_content.append(self._header(repo['name']))
      lst_content.append(self._item('Status', repo['status_description']))
      lst_content.append(self._item('Description', repo['description'] if repo['description'] else '-'))
      lst_content.append(self._item('Pulls', repo['pull_count']))
      lst_content.append(self._item('Registered', self._format_date(repo['date_registered'])))
      lst_content.append(self._item('Updated', self._format_date(repo['date_registered'])))
      lst_content.append(self._item('Categories', ', '.join([v['name'] for v in repo['categories']])))
      lst_content.append(self._item('Size', self._format_bytes(repo['storage_size'])))
      if len(repo['tags']['content']):
        tag_count = repo['tags']['meta']['tag_count']
        message = self._note('(only showing the latest 10 tags)') if tag_count > 10 else ''
        lst_content.append(self._item('Tags', f'{tag_count} {message}'))
        for tag in repo['tags']['content']:
          lst_content.append(self._item('Tag', tag['name'], prefix='- '))
          lst_content.append(self._item('Size', self._format_bytes(tag['full_size']), indent=2))
          lst_content.append(self._item('Last push', self._format_date(tag['tag_last_pushed']), indent=2))

          digest = f'`{tag['digest'].split(':')[1][0:12]}`' if 'digest' in tag else '-'
          lst_content.append(self._item('Digest', digest, indent=2))

    file = "dockerhub/repositories.md"
    return {file: lst_content}

  def __users_teams_to_markdown(self, dict_users_teams):
    lst_content = list()

    # Info block
    lst_content.append(">[!info] General information")
    lst_content.append(self._item('Number of teams', dict_users_teams['meta']['team_count']))
    lst_content.append(self._item('Number of users', dict_users_teams['meta']['user_count']))
    lst_content.append("")

    # Teams
    lst_content.append(self._header('Teams'))
    for team in dict_users_teams['content']['teams']:
      lst_content.append(self._header(team['name'], 4))
      lst_content.append(self._item('Member count', team['member_count']))
      lst_content.append(self._item('Members', ', '.join(team['members'])))

    # Users
    lst_content.append(self._header('Users'))
    for user in dict_users_teams['content']['users']:
      lst_content.append(self._header(user['username'], 4))
      lst_content.append(self._item('Name', user['full_name'] if user['full_name'] else '-'))
      lst_content.append(self._item('Email', user['email']))
      lst_content.append(self._item('Role', user['role']))
      lst_content.append(self._item('Type', user['type']))
      lst_content.append(self._item('Joined', self._format_date(user['date_joined'])))

    file = "dockerhub/users_teams.md"
    return {file: lst_content}

  def _build_content(self):
    md_main = dict()

    # Users and teams
    teams_users = self.__enumerate_teams_users()
    md_main.update(self.__users_teams_to_markdown(teams_users))

    # Repositories
    repositories = self.__enumerate_repositories()
    md_main.update(self.__repositories_to_markdown(repositories))

    return md_main