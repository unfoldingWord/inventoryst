from .Platform import Platform
from github import Github as Gh
from pprint import pp
import re
from dateutil.relativedelta import relativedelta
from datetime import datetime, timezone

class Github(Platform):
  def __init__(self):
    super().__init__()

    # Load config
    self.__config = self.load_config('github')

    # Determine organization to inventorize for today
    dict_org = self.__determine_org(self.__config)
    self.__org, gh_token = list(dict_org.items())[0]

    # Github module
    self.__github_api = Gh(gh_token)
    self.__github_api.per_page = 100

    # Set org
    self.__obj_org = self.__github_api.get_organization(self.__org)

    # Need manual API connections for specific purposes
    self.__github_api_url = 'https://api.github.com/'
    self.__headers = [
      ['Authorization', 'Bearer ' + gh_token],
      [ 'X-GitHub-Api-Version', '2022-11-28']
    ]

  def __determine_org(self, gh_config):
    orgs = gh_config['orgs']

    # We only inventorize one organization per day because of the amount of requests.
    # Monday is 0 and Sunday is 6.
    weekday = datetime.weekday(datetime.now())
    if weekday == 6:
      # On Sundays, we rest, as suggested by my daughter :)
      return None
    elif weekday < 3:
      org = orgs[weekday]
    else:
      org = orgs[weekday % len(orgs)]

    return org

  def __get_commit_count(self, repo: str):
    url = f'{self.__github_api_url}/repos/{repo}/commits?per_page=1&page=1'
    results = self._get_json_from_url(url, headers=self.__headers, raw=True)

    links = results.headers['Link'].split(',')
    commits = re.findall(r'&page=(\d+)', links[-1])

    return commits[0]

  def __enumerate_dependabot_alerts(self, obj_repo):
    # First check if this repo has dependabot alerts enabled
    repo_name = obj_repo.full_name
    check_url = f"{self.__github_api_url}/repos/{repo_name}/vulnerability-alerts"
    result = self._get_json_from_url(check_url, self.__headers, raw=True)

    # If Vulnerability alerts are NOT enabled, a 404 is returned.
    if result.status_code == 404:
      return None

    lst_alerts = list()

    dependabot_alerts = obj_repo.get_dependabot_alerts(state='open')
    self._inc_api_call()

    field_filter = ['security_vulnerability', 'html_url', 'updated_at']
    for alerts in dependabot_alerts:
      dict_alert = self._filter_fields(alerts, field_filter)
      lst_alerts.append(dict_alert)

    return lst_alerts

  def __enumerate_repos(self, org: str):
    dict_repos = dict()
    dict_repos["meta"] = dict()
    dict_repos["content"] = list()

    repos = self.__github_api.get_organization(org).get_repos(sort='pushed', direction='desc')
    self._inc_api_call(2)

    field_filter = ['name', 'full_name', 'html_url', 'archived', 'visibility', 'pushed_at', 'description',
                    'size', 'default_branch']

    repo_count = 0
    repo_archived_count = 0
    repo_stale_count = 0
    repo_private_count = 0
    repo_total_size = 0
    repo_with_sec_alert_counts = 0
    for obj_repo in repos:

      repo_count += 1

      # Standard fields
      dict_repo = self._filter_fields(obj_repo, field_filter)

      # Getting totals for several metrics
      repo_total_size += dict_repo['size']

      if dict_repo['archived'] is True:
        repo_archived_count += 1

      if dict_repo['visibility'] == 'private':
        repo_private_count += 1

      # Non-archived repo's with last push older than 2 years is considered stale
      dict_repo['stale'] = False
      stale_years = self.__config['stale_years']
      if dict_repo['archived'] is False and relativedelta(datetime.now(timezone.utc), dict_repo['pushed_at']).years >= stale_years:
        dict_repo['stale'] = True
        repo_stale_count += 1

      # Check if repo is empty (size = 0)
      # Additional information is not available or relevant for an empty (uninitialized) repo
      if dict_repo['size'] > 0:

        # Number of commits
        dict_repo['commit_count'] = self.__get_commit_count(dict_repo['full_name'])

        # Contributors
        contributors = obj_repo.get_stats_contributors()
        self._inc_api_call()
        dict_repo['contributors'] = [c.author.login for c in contributors] if contributors else None

        # Dependabot alerts (only if the repo is NOT archived)
        if dict_repo['archived'] is False:
          dependabot_alerts = self.__enumerate_dependabot_alerts(obj_repo)
          if dependabot_alerts and len(dependabot_alerts) > 0:
            repo_with_sec_alert_counts += 1

          dict_repo['dependabot_alerts'] = dependabot_alerts

        # Releases (count)
        releases = obj_repo.get_releases()
        self._inc_api_call()
        dict_repo['release_count'] = len([r for r in releases])

      else:
        # Empty repo
        dict_repo['commit_count'] = 0
        dict_repo['contributors'] = []
        dict_repo['release_count'] = 0


      # Done. Affix and next
      dict_repos['content'].append(dict_repo)

    # Add totals
    dict_repos['meta']['repo_count'] = repo_count
    dict_repos['meta']['repo_stale_count'] = repo_stale_count
    dict_repos['meta']['repo_archived_count'] = repo_archived_count
    dict_repos['meta']['repo_private_count'] = repo_private_count
    dict_repos['meta']['repo_with_sec_alerts_count'] = repo_with_sec_alert_counts
    dict_repos['meta']['repo_total_size'] = repo_total_size

    return dict_repos

  def __get_team_members(self, obj_team):
    lst_return = list()

    members = obj_team.get_members()
    self._inc_api_call()
    for member in members:
      lst_return.append(member.login)

    return lst_return

  def __enumerate_teams(self):
    dict_teams = dict()
    dict_teams['meta'] = dict()
    dict_teams['content'] = list()

    team_filter = ['name', 'html_url', 'description', 'privacy', 'permission']

    teams = self.__obj_org.get_teams()
    self._inc_api_call()

    team_count = 0
    for team in teams:
      team_count += 1

      # Default fields
      dict_team = self._filter_fields(team, team_filter)

      # Get team members
      dict_team['members'] = self.__get_team_members(obj_team=team)

      dict_teams['content'].append(dict_team)

    dict_teams['meta']['team_count'] = team_count
    return dict_teams

  def __enumerate_users(self):
    # Return both members of the organisation and outside collaborators

    dict_users = dict()
    dict_users['meta'] = dict()
    dict_users['content'] = list()

    # Get all members
    users = self.__obj_org.get_members()
    self._inc_api_call()

    # Get all collaborators
    collaborators = self.__obj_org.get_outside_collaborators()
    self._inc_api_call()

    # Get all members that have no 2FA enabled
    users_no2fa = self.__obj_org.get_members(filter_='2fa_disabled')
    self._inc_api_call()

    # Get all collaborators that have no 2FA enabled
    collaborators_no2fa = self.__obj_org.get_outside_collaborators(filter_='2fa_disabled')
    self._inc_api_call()
    lst_users_no2fa = list()

    # Add No2FA users and collaborators to a simple list
    for user in users_no2fa:
      lst_users_no2fa.append(user.login)

    for user in collaborators_no2fa:
      lst_users_no2fa.append(user.login)

    # Let's go
    user_filter = ['login', 'html_url', 'avatar_url', 'type']
    member_count = 0
    collaborator_count = 0

    # Members of the organisation
    users_no2fa_count = 0
    for user in users:
      member_count += 1

      # Default fields
      dict_user = self._filter_fields(user, user_filter)

      # Last active
      events = user.get_events()
      self._inc_api_call()

      last_active = None
      for event in events:
        last_active = event.last_modified
        break

      dict_user['last_active'] = last_active

      # 2FA disabled
      dict_user['2fa_disabled'] = False
      if dict_user['login'] in lst_users_no2fa:
        users_no2fa_count += 1
        dict_user['2fa_disabled'] = True

      # add to main
      dict_users['content'].append(dict_user)

    # Outside Collaborators
    for user in collaborators:
      collaborator_count += 1

      # Default fields
      dict_user = self._filter_fields(user, user_filter)

      # Is collaborator
      dict_user['outside_collaborator'] = True

      # Last active
      events = user.get_events()
      self._inc_api_call()

      last_active = None
      for event in events:
        last_active = event.last_modified
        break

      dict_user['last_active'] = last_active

      # 2FA disabled
      dict_user['2fa_disabled'] = False
      if dict_user['login'] in lst_users_no2fa:
        users_no2fa_count += 1
        dict_user['2fa_disabled'] = True

      # add to main
      dict_users['content'].append(dict_user)

    # Sort the whole list of users on login name
    # This mixes both members and collaborators
    dict_users['content'] = sorted(dict_users['content'], key=lambda d: d['login'].lower())


    dict_users['meta']['member_count'] = member_count
    dict_users['meta']['collaborator_count'] = collaborator_count
    dict_users['meta']['user_no2fa_count'] = users_no2fa_count
    return dict_users


  def __markdown_repos(self, org: str, dict_repos: dict):
    lst_content = list()

    # Info block
    lst_content.append(">[!info] General information")
    lst_content.append(self._item('Repositories total', dict_repos['meta']['repo_count']))
    lst_content.append(self._item('Private', dict_repos['meta']['repo_private_count']))
    lst_content.append(self._item('Archived', dict_repos['meta']['repo_archived_count']))
    lst_content.append(self._item('Stale', dict_repos['meta']['repo_stale_count']))
    lst_content.append(self._item('With Dependabot alerts', dict_repos['meta']['repo_with_sec_alerts_count']))
    lst_content.append(self._item('Total size', self._format_bytes(dict_repos['meta']['repo_total_size'] * 1024)))
    lst_content.append("")

    for repo in dict_repos['content']:
      # Handling labels
      # Stale
      label_stale = ''
      if repo['stale'] is True:
        label_stale = self._highlight('Stale', color='#bbbfc5', border_color='#bbbfc5')
      # Archived
      label_archived = ''
      if repo['archived'] is True:
        label_archived = self._highlight('Archived', color='#a9470f', background='#fff4dc')
      # Private
      label_private = ''
      if repo['visibility'] == 'private':
        label_private = self._highlight('Private', color='#cccccc', border_color='#cccccc')
      # Empty
      label_empty = ''
      if repo['size'] == 0:
        label_empty = self._highlight('Empty', color='orange', border_color='orange')

      lst_content.append(self._header(f"{repo['name']} {label_private} {label_empty} {label_archived}{label_stale}", size=4))

      lst_content.append(self._highlight(repo['description'], 'gray', weight='normal') if repo['description'] else '-')
      lst_content.append(self._item('URL', repo['html_url']))
      lst_content.append(self._item('Default branch', repo['default_branch']))
      lst_content.append(self._item('Commits', repo['commit_count']))
      lst_content.append(self._item('Last push', self._format_date(repo['pushed_at'])))
      lst_content.append(self._item('Size', self._format_bytes(repo['size'] * 1024)))
      lst_content.append(self._item('Releases', repo['release_count']))
      contributors = '-'
      if repo['contributors']:
        contributors = ', '.join([c for c in repo['contributors']])
      lst_content.append(self._item('Contributors', contributors))

      # Dependabot alerts
      severity_to_color = {
        'low': ['khaki', 'black'],
        'medium': ['yellow', 'black'],
        'high': ['orange', 'black'],
        'critical': ['red', 'white'],
      }

      if 'dependabot_alerts' in repo:
        if repo['dependabot_alerts'] is None:
          # Alerts are NOT enabled, this is not a good situation
          dependabot_alerts = self._highlight('Disabled', 'white', 'red')
        else:
          if len(repo['dependabot_alerts']):
            dependabot_alerts = ''
            for alert in repo['dependabot_alerts']:
              button_color = severity_to_color[alert['security_vulnerability'].severity][0]
              text_color = severity_to_color[alert['security_vulnerability'].severity][1]
              button = self._highlight(alert['security_vulnerability'].package.name, color=text_color, background=button_color, weight='normal')

              dependabot_alerts += f"{button} "
          else:
            dependabot_alerts = self._highlight('None', color='white', background='green', weight='normal')


        link = self._link(f"{repo['html_url']}/security/dependabot", 'Dependabot alerts')
        lst_content.append(self._item(link, dependabot_alerts))

    file = f"github/{org}/repositories.md"
    return {file: lst_content}

  def __markdown_teams_and_users(self, org: str, teams: dict, users: dict):
    lst_content = list()

    # Info block
    lst_content.append(">[!info] General information")
    lst_content.append(self._item('Teams', teams['meta']['team_count']))
    lst_content.append(self._item('Members', users['meta']['member_count']))
    lst_content.append(self._item('Collaborators', users['meta']['collaborator_count']))
    lst_content.append(self._item('Users without 2FA', users['meta']['user_no2fa_count']))
    lst_content.append("")

    # Teams
    lst_content.append(self._header("Teams"))
    for team in teams['content']:

      lst_content.append(self._header(team['name'], 3))

      description = team['description'] if team['description'] else '-'
      lst_content.append(self._note(description))

      lst_content.append(self._item('URL', team['html_url']))
      lst_content.append(self._item('Privacy', team['privacy']))
      lst_content.append(self._item('Permissions', team['permission']))
      lst_content.append(self._item('Members', ', '.join(team['members'])))

    # Users
    lst_content.append(self._header('Users'))
    for user in users['content']:
      label_no2fa = ''
      if user['2fa_disabled'] is True:
        label_no2fa = self._highlight('No 2FA', color='white', background='red')

      lst_content.append(self._header(f"{user['login']} {label_no2fa}", 3))
      lst_content.append(f"{self._avatar(user['avatar_url'])} {self._item('URL', user['html_url'])}")
      lst_content.append(self._item('Type', user['type']))

      # Member or outside collaborator
      user_type = 'Member'
      if 'outside_collaborator' in user:
        user_type = 'Outside collaborator'
      lst_content.append(self._item('Affiliation', user_type))

      last_active = self._format_date(user['last_active']) if user['last_active'] else '-'
      lst_content.append(self._item('Last active', last_active))

    file = f"github/{org}/users_and_teams.md"
    return {file: lst_content}


  def _build_content(self):
    md_main = dict()

    self._logger.debug(self.__github_api.get_rate_limit())

    #repos = self.__enumerate_repos(self.__org)
    #md_main.update(self.__markdown_repos(self.__org, repos))

    teams = self.__enumerate_teams()
    users = self.__enumerate_users()
    md_main.update(self.__markdown_teams_and_users(self.__org, teams, users))

    self._logger.debug(self.__github_api.get_rate_limit())

    return md_main


  def __del__(self):
    self.__github_api.close()
