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
          dict_repo['dependabot_alerts'] = self.__enumerate_dependabot_alerts(obj_repo)

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
    dict_repos['meta']['repo_total_size'] = repo_total_size

    return dict_repos

  def __markdown_repos(self, org: str, dict_repos: dict):
    lst_content = list()

    # Info block
    lst_content.append(">[!info] General information")
    lst_content.append(self._item('Repositories total', dict_repos['meta']['repo_count']))
    lst_content.append(self._item('Private', dict_repos['meta']['repo_private_count']))
    lst_content.append(self._item('Archived', dict_repos['meta']['repo_archived_count']))
    lst_content.append(self._item('Stale', dict_repos['meta']['repo_stale_count']))
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
        'low': ['green', 'black'],
        'medium': ['yellow', 'black'],
        'high': ['orange', 'black'],
        'critical': ['red', 'white'],
      }

      if 'dependabot_alerts' in repo:
        if repo['dependabot_alerts'] is None:
          # Alerts are NOT enabled, this is not a good situation
          dependabot_alerts = self._highlight('Disabled', 'white', 'red')
        else:
          dependabot_alerts = '-'
          for alert in repo['dependabot_alerts']:
            button_color = severity_to_color[alert['security_vulnerability'].severity][0]
            text_color = severity_to_color[alert['security_vulnerability'].severity][1]
            button = self._highlight(alert['security_vulnerability'].package.name, color=text_color, background=button_color, weight='normal')

            dependabot_alerts += f"{button} "

        link = self._link(f"{repo['html_url']}/security/dependabot", 'Dependabot alerts')
        lst_content.append(self._item(link, dependabot_alerts))

    file = f"github/{org}/repositories.md"
    return {file: lst_content}


  def _build_content(self):
    md_main = dict()

    self._logger.debug(self.__github_api.get_rate_limit())

    repos = self.__enumerate_repos(self.__org)
    md_main.update(self.__markdown_repos(self.__org, repos))

    self._logger.debug(self.__github_api.get_rate_limit())

    return md_main


  def __del__(self):
    self.__github_api.close()
