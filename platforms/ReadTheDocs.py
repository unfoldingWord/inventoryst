from .Platform import Platform

class ReadTheDocs(Platform):
    def __init__(self):
        super().__init__()

        self.__config = self.load_config('readthedocs')

        self.__api_url = 'https://readthedocs.org/api/v3/'
        api_key = self.__config['api_key']

        self.__headers = [['Authorization', 'Token ' + api_key]]

    def __get_build_details(self, slug):
        url_builds = f"{self.__api_url}/projects/{slug}/builds/"

        dict_builds = self._get_json_from_url(url=url_builds, headers=self.__headers)

        # RtD returns builds in reverse order of build dates. So last build comes first!
        last_build = dict_builds['results'][0]

        return {
            "success": last_build["success"],
            "date_finished": last_build["finished"]
        }

    def __enumerate_projects(self):
        dict_projects = dict()
        dict_projects["meta"] = dict()
        dict_projects["content"] = list()

        # Get the projects
        url_projects = f'{self.__api_url}/projects/?limit=30'
        projects = self._get_json_from_url(url=url_projects, headers=self.__headers)

        dict_projects["meta"]["project_count"] = projects["count"]

        field_filter = ['name', 'created', 'modified']
        for project in projects["results"]:
            dict_project = self._filter_fields(project, field_filter)

            # Get build details
            dict_last_build = self.__get_build_details(project['slug'])
            build_status = "success" if dict_last_build['success'] is True else "failed"
            dict_project['last_build_status'] = build_status

            dict_project['last_build'] = dict_last_build["date_finished"]

            dict_project['repository'] = project['repository']['url']
            dict_project['documentation'] = project['urls']['documentation']
            dict_project['home'] = project['urls']['home']

            dict_project['users'] = [user['username'] for user in project['users']]

            dict_projects["content"].append(dict_project)

        return dict_projects

    def __markdown_projects(self, inventory):

        lst_content = list()

        # General information
        lst_content.append(">[!info] General information")
        lst_content.append(self._item('Overview', self._link('https://readthedocs.org/dashboard', 'dashboard')))
        lst_content.append(self._item('Number of projects', inventory["meta"]["project_count"]))
        lst_content.append("")

        # List the projects
        for item in inventory["content"]:

            lst_content.append(self._header(self._link(item['home'], item['name']), 3))
            lst_content.append(self._item('Created', self._format_date(item['created'])))
            lst_content.append(self._item('Modified', self._format_date(item['modified'])))
            lst_content.append(self._item('Repository', item['repository']))

            # Last build
            if item['last_build']:
                last_built = self._format_date(item['last_build'])
            else:
                last_built = ''
            build_color = "green" if item["last_build_status"] == 'success' else "red"
            build_status = self._highlight(item["last_build_status"], color='white', background=build_color, border_color='white')
            lst_content.append(self._item('Last built', f'{last_built} {build_status}'))

            # Users
            users = ", ".join(["[" + user + "](https://www.github.com/" + user + ")" for user in item['users']])
            lst_content.append(self._item('Users', users))
            lst_content.append("")

        # return it all
        platform_file = 'readthedocs.md'
        return {platform_file: lst_content}

    def _build_content(self):
        md_main = dict()

        inventory = self.__enumerate_projects()
        md_main.update(self.__markdown_projects(inventory))

        return md_main
