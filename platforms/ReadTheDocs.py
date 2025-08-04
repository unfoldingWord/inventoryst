from dateutil import parser, relativedelta

from .Platform import Platform


class ReadTheDocs(Platform):
    def __init__(self):
        super().__init__()
        self.api_url = self._get_env('READTHEDOCS_API_URL')
        self.api_key = self._get_env('READTHEDOCS_API_KEY')

    def __get_build_details(self, slug):
        url_builds = self.api_url + f"/projects/{slug}/builds/"

        dict_builds = self._get_json_from_url(url=url_builds, headers=[['Authorization', 'Token ' + self.api_key]])

        # RtD returns builds in reverse order of build dates. So last build comes first!
        last_build = dict_builds['results'][0]

        return {
            "success": last_build["success"],
            "date_finished": last_build["finished"]
        }

    def __get_readable_timedelta(self, date):
        # Currently, this function is not being used
        # Keeping it for maybe later usage
        my_date = parser.parse(date)

        fancy_delta = relativedelta.relativedelta(self._now, my_date)

        shiny_list = list()

        if fancy_delta.years > 0:
            suffix = " year" if fancy_delta.years == 1 else " years"
            shiny_list.append(str(fancy_delta.years) + suffix)

        if fancy_delta.months > 0:
            suffix = " month" if fancy_delta.months == 1 else " months"
            shiny_list.append(str(fancy_delta.months) + suffix)

        if fancy_delta.weeks > 0:
            suffix = " week" if fancy_delta.weeks == 1 else " weeks"
            shiny_list.append(str(fancy_delta.weeks) + suffix)

        if fancy_delta.days > 0:
            suffix = " day" if fancy_delta.days == 1 else " days"
            shiny_list.append(str(fancy_delta.days) + suffix)

        if fancy_delta.hours > 0:
            suffix = " hour" if fancy_delta.months == 1 else " hours"
            shiny_list.append(str(fancy_delta.hours) + suffix)

        if fancy_delta.minutes > 0:
            suffix = " minute" if fancy_delta.months == 1 else " minutes"
            shiny_list.append(str(fancy_delta.minutes) + suffix)

        # Only use first two elements (a la RtD)
        shiny_list = shiny_list[:2]

        return ", ".join(shiny_list) + " ago"

    def __enumerate(self):
        url_projects = self.api_url + '/projects/?limit=30'
        dict_projects = dict()
        dict_projects["meta"] = dict()
        dict_projects["content"] = list()

        projects = self._get_json_from_url(url=url_projects, headers=[['Authorization', 'Token ' + self.api_key]])

        dict_projects["meta"]["project_count"] = projects["count"]

        for item in projects["results"]:
            # Get build details
            dict_last_build = self.__get_build_details(item['slug'])
            build_status = "success" if dict_last_build['success'] is True else "failed"

            dict_project = dict()
            dict_project['name'] = item['name']

            dict_project['created'] = item['created']
            dict_project['last_modified'] = item['modified']
            dict_project['last_build'] = dict_last_build["date_finished"]
            dict_project['last_build_status'] = build_status

            dict_project['repository'] = item['repository']['url']
            dict_project['documentation'] = item['urls']['documentation']
            dict_project['home'] = item['urls']['home']

            users = [user['username'] for user in item['users']]
            dict_project['users'] = users

            dict_projects["content"].append(dict_project)

        return dict_projects

    def _build_content(self):
        inventory = self.__enumerate()
        return self.__to_markdown(inventory)

    def __to_markdown(self, inventory):

        lst_content = list()

        # General information
        lst_content.append(">[!info] General information")
        lst_content.append(">**Overview:** [dashboard](https://readthedocs.org/dashboard)")
        lst_content.append("**Number of projects:** " + str(inventory["meta"]["project_count"]))
        lst_content.append("")

        # List the projects
        for item in inventory["content"]:
            created = parser.parse(item['created']).strftime("%B %-d, %Y")
            if item['last_build']:
                last_built = parser.parse(item['last_build']).strftime("%a, %b %-d, %Y, %-I:%M %p")
            else:
                last_built = '-'
            last_modified = parser.parse(item['last_modified']).strftime("%a, %b %-d, %Y, %-I:%M %p")

            build_color = "green" if item["last_build_status"] == 'success' else "red"

            lst_content.append("### [" + item['name'] + "](" + item['home'] + ")")
            lst_content.append("**Created:** " + created)
            lst_content.append("**Last modified:** " + last_modified)
            lst_content.append("**Last built:** " + last_built +
                               f" <span style=\"color: {build_color}; font-weight: bold\"> " +
                               "[" + item["last_build_status"] + "] </span>")
            lst_content.append("**Repository:** " + item['repository'])

            lst_users = ["[" + user + "](https://www.github.com/" + user + ")" for user in item['users']]

            lst_content.append("**Users:** " + ", ".join(lst_users))
            lst_content.append("")

        # return it all
        platform_file = self._get_env('READTHEDOCS_MD_FILE')

        return {platform_file: lst_content}
