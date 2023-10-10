import os.path
import datetime
from dateutil import parser, relativedelta
from .Platform import Platform
from pprint import pprint


class ReadtheDocs(Platform):
    def __init__(self):
        super().__init__()
        self.api_url = self._get_env('READTHEDOCS_API_URL')
        self.api_key = self._get_env('READTHEDOCS_API_KEY')

    def inventorize(self):
        inventory = self.__enumerate()
        self.__export_to_markdown_files(inventory)

        # @TODO something needs to be returned to caller, so the index.md can be built

    def __get_build_details(self, slug):
        url_builds = self.api_url + f"/projects/{slug}/builds/"

        dict_builds = self._get_json_from_url(url=url_builds, token=self.api_key)

        # RtD returns builds in reverse order of build dates. So last build comes first!
        last_build = dict_builds['results'][0]

        return {
            "success": last_build["success"],
            "date_finished": last_build["finished"]
        }

    def __get_readable_timedelta(self, date):
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

        projects = self._get_json_from_url(url=url_projects, token=self.api_key)
        #pprint (projects)

        dict_projects["meta"]["project_count"] = projects["count"]

        for item in projects["results"]:

            # Get build details
            dict_last_build = self.__get_build_details(item['slug'])
            build_status = "success" if dict_last_build['success'] is True else "failed"

            last_build = self.__get_readable_timedelta(dict_last_build["date_finished"])

            dict_project = dict()
            dict_project['name'] = item['name']

            dict_project['created'] = item['created']
            dict_project['last_modified'] = item['modified']
            dict_project['last_build'] = last_build
            dict_project['last_build_status'] = build_status

            dict_project['repository'] = item['repository']['url']
            dict_project['documentation'] = item['urls']['documentation']
            dict_project['home'] = item['urls']['home']

            users = [user['username'] for user in item['users']]
            dict_project['users'] = users

            dict_projects["content"].append(dict_project)

        return dict_projects

    def __export_to_markdown_files(self, inventory):
        # pprint(inventory)

        base_path = self._get_env('OUTPUT_DIRECTORY')
        platform_file = self._get_env('READTHEDOCS_MD_FILE')

        if not os.path.exists(base_path):
            raise FileExistsError(f"The directory '{base_path}' does not exist. Exiting.")

        with open(base_path + "/" + platform_file, 'w') as md_file:
            md_file.write(self._get_header_warning() + "\n")

            # General information
            md_file.write(">[!info] General information\n")
            md_file.write(">**Overview:** [dashboard](https://readthedocs.org/dashboard)\n")
            md_file.write("**Number of projects:** " + str(inventory["meta"]["project_count"]) + "\n\n")

            # List the projects
            for item in inventory["content"]:
                created = parser.parse(item['created']).strftime("%B %-d, %Y")
                last_modified = parser.parse(item['last_modified']).strftime("%B %-d, %Y")

                md_file.write("### [" + item['name'] + "](" + item['home'] + ")\n")
                md_file.write("**Created:** " + created + "\n")
                md_file.write("**Last modified:** " + last_modified + "\n")
                md_file.write("**Last built:** " + item['last_build'] +
                              r" **\[" + item["last_build_status"] + r"\]**" + "\n")
                md_file.write("**Repository:** " + item['repository'] + "\n")

                lst_users = ["[" + user + "](https://www.github.com/" + user + ")" for user in item['users']]

                md_file.write("**Users:** " + ", ".join(lst_users) + "\n")
                md_file.write("\n")
                #md_file.write("---\n")



        # Needs to return to main, as main is writing the index


