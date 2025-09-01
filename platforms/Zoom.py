from .Platform import Platform
import os
import base64
import requests
from dateutil import parser as date_parser, relativedelta
import datetime
import pprint

# https://marketplace.zoom.us/develop/apps/
# https://developers.zoom.us/docs/api/


class Zoom(Platform):
    def __init__(self):
        super().__init__()

        self.access_token = self.__request_access_token()

    def __request_access_token(self):
        account_id = os.getenv('ZOOM_ACCOUNT_ID')
        client_id = os.getenv('ZOOM_CLIENT_ID')
        client_secret = os.getenv('ZOOM_CLIENT_SECRET')
        zoom_api = 'https://zoom.us/oauth/token'

        encoded_auth = base64.b64encode((client_id + ":" + client_secret).encode('utf-8')).decode('utf-8')

        dict_headers = dict()
        dict_headers['Content-Type'] = "application/x-www-form-urlencoded"
        dict_headers['Authorization'] = "Basic " + str(encoded_auth)

        dict_post_data = dict()
        dict_post_data['grant_type'] = 'account_credentials'
        dict_post_data['account_id'] = account_id

        response = requests.post(zoom_api, dict_post_data, headers=dict_headers)

        return response.json()['access_token']

    def __make_api_request(self, api_url):

        dict_headers = dict()
        dict_headers['Content-Type'] = "application/x-www-form-urlencoded"
        dict_headers['Authorization'] = "Bearer " + self.access_token

        if '?' in api_url:
            qs = '&page_size=100'
        else:
            qs = '?page_size=100'

        response = requests.get(api_url + qs, headers=dict_headers)
        return response.json()

    def __month_range(self, start_date, end_date):

        year = start_date.year
        month = start_date.month

        dict_month_range = dict()

        while (year, month) <= (end_date.year, end_date.month):
            start_of_month = datetime.date(year, month, 1)
            end_of_month = start_of_month + relativedelta.relativedelta(day=31)

            if end_of_month > end_date:
                end_of_month = end_date

            dict_month_range[str(start_of_month)] = str(end_of_month)

            # Move to the next month.  If we're at the end of the year, wrap around
            # to the start of the next.
            #
            # Example: Nov 2017
            #       -> Dec 2017 (month += 1)
            #       -> Jan 2018 (end of year, month = 1, year += 1)
            #
            if month == 12:
                month = 1
                year += 1
            else:
                month += 1

        return dict_month_range

    def __get_plan_usage(self):
        usage = self.__make_api_request('https://api.zoom.us/v2/accounts/me/plans/usage')
        # pprint.pprint(usage)
        return usage

    def __get_recording_stats(self, user_id):
        # As of my current knowledge, there is no way to know if a user even has recordings or not.
        # We can only request recordings per user, even more limited by the fact that we can only
        # request recordings over a period of maximum a month.
        # This forces us to iterate, per user, over all the months that recordings could have taken place
        # Therefore, this is a very expensive operation. As of the moment of writing,
        # this results in 34 users x 48 months = 1632 API requests, taking up to 20 minutes!

        # Oldest recording (manually checked) is 2020-08-01
        # Recordings can only be fetched per month, so we need to query multiple times
        start_date = datetime.date(2020, 8, 1)
        end_date = datetime.date.today()

        range_months = self.__month_range(start_date, end_date)
        # pprint.pprint(range_months)

        total_recording_number = 0
        total_recording_size = 0
        total_recording_length = 0

        for start_date in range_months:
            end_date = range_months[start_date]
            api_url = f'https://api.zoom.us/v2/users/{user_id}/recordings?from={start_date}&to={end_date}'
            # print(api_url)

            recordings = self.__make_api_request(api_url)
            if recordings['total_records'] > 0:
                # pprint.pprint(recordings)

                total_recording_number += recordings['total_records']

                for recording in recordings['meetings']:
                    total_recording_length += recording['duration']

                    for file in recording['recording_files']:
                        total_recording_size += file['file_size']

        dict_recording_stats = {
            'total_recordings': total_recording_number,
            'total_recordings_size': total_recording_size,
            'total_recordings_length': total_recording_length
        }

        return dict_recording_stats

    def __get_user(self, user_id):
        user = self.__make_api_request(f'https://api.zoom.us/v2/users/{user_id}')

        return user

    def __enumerate_rooms(self):
        dict_rooms = dict()
        dict_rooms["meta"] = dict()
        dict_rooms["content"] = list()

        rooms = self.__make_api_request('https://api.zoom.us/v2/rooms')
        pprint.pprint(rooms)

        dict_rooms["meta"]["room_count"] = len(rooms['rooms'])

        for room in rooms['rooms']:
            tmp_room = dict()

            tmp_room['name'] = room['name']
            tmp_room['room_id'] = room['room_id']

            dict_rooms['content'].append(tmp_room)

        return dict_rooms

    def __enumerate_users(self):
        dict_users = dict()
        dict_users["meta"] = dict()
        dict_users["content"] = list()

        dict_plan_usage = self.__get_plan_usage()

        users = self.__make_api_request('https://api.zoom.us/v2/users')
        # pprint.pprint(users)
        # exit()

        # Users
        dict_users["meta"]["user_count"] = users['total_records']

        nr_of_owners = len([user for user in users['users'] if user['role_id'] == '0'])
        dict_users["meta"]["owner_count"] = nr_of_owners

        nr_of_admins = len([user for user in users['users'] if user['role_id'] == '1'])
        dict_users["meta"]["admin_count"] = nr_of_admins

        nr_of_members = len([user for user in users['users'] if user['role_id'] == '2'])
        dict_users["meta"]["member_count"] = nr_of_members

        # Licences
        dict_users["meta"]["licenses_available"] = dict_plan_usage['plan_base']['hosts']
        dict_users["meta"]["licenses_used"] = dict_plan_usage['plan_base']['usage']

        # Recordings
        dict_users["meta"]["recording_storage"] = dict_plan_usage['plan_recording']['free_storage']
        dict_users["meta"]["recording_storage_used"] = dict_plan_usage['plan_recording']['free_storage_usage']

        rec_fetch_limit = 0
        for user in users['users']:

            dict_additional_user_data = self.__get_user(user['id'])

            tmp_user = dict()
            tmp_user['id'] = user['id']
            tmp_user['full_name'] = user['first_name'] + ' ' + user['last_name']
            tmp_user['display_name'] = user['display_name']
            tmp_user['email'] = user['email']
            tmp_user['pmi'] = user['pmi']
            tmp_user['personal_meeting_url'] = dict_additional_user_data['personal_meeting_url']
            if 'last_client_version' in user:
                tmp_user['last_client_version'] = user['last_client_version']
            tmp_user['last_login'] = user['last_login_time']
            tmp_user['verified'] = user['verified']
            tmp_user['type'] = user['type']
            tmp_user['role_id'] = user['role_id']
            if 'pic_url' in user:
                tmp_user['avatar'] = user['pic_url']

            # Recordings statistics
            # On development, we only try to fetch recordings for a few users,
            # as this is an expensive (time-wise) operation
            if rec_fetch_limit < 3:
                recordings = self.__get_recording_stats(user['id'])
                tmp_user['recording_stats'] = recordings
                if os.getenv('STAGE') == 'dev':
                    rec_fetch_limit += 1

            dict_users['content'].append(tmp_user)

        return dict_users

    def __format_bytes(self, size):
        # 2**10 = 1024
        power = 2 ** 10
        n = 0
        power_labels = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
        while size > power:
            size /= power
            n += 1
        return size, power_labels[n] + 'B'

    def __users_to_markdown(self, inventory):

        lst_content = list()

        lst_content.append(">[!info] General information")
        lst_content.append("**[Users total](https://us02web.zoom.us/account/user#/):** " +
                           str(inventory["meta"]["user_count"]))
        lst_content.append("**Owners:** " + str(inventory["meta"]["owner_count"]))
        lst_content.append("**Admins:** " + str(inventory["meta"]["admin_count"]))
        lst_content.append("**Members:** " + str(inventory["meta"]["member_count"]))
        lst_content.append('>\n>---')
        lst_content.append("**[Licenses](https://admin.zoom.us/billing):** " +
                           str(inventory["meta"]["licenses_available"]))
        lst_content.append("**Licenses used:** " + str(inventory["meta"]["licenses_used"]))
        lst_content.append('>\n>---')
        lst_content.append("**[Recording storage](https://admin.zoom.us/recording/management):** " +
                           str(inventory["meta"]["recording_storage"]))
        lst_content.append("**Recording storage used:** " + str(inventory["meta"]["recording_storage_used"]))

        lst_content.append("")

        lst_users = sorted(inventory["content"], key=lambda item: item["full_name"])

        for dict_user in lst_users:
            if 'avatar' in dict_user:
                avatar = '<img src="' + dict_user['avatar'] + '" style="width: 75px; float: left; margin-right: 10px" />'
            else:
                avatar = ''

            if dict_user['full_name'] == dict_user['display_name']:
                display_name = dict_user['full_name']
            else:
                display_name = dict_user['full_name'] + " (" + dict_user['display_name'] + ")"
            # Paste avatar image in front of name for proper alignment
            lst_content.append(avatar + "**Name:** " + display_name)

            lst_content.append("**PMI:** " + str(dict_user['pmi']))
            lst_content.append("**Personal meeting URL:** " + dict_user['personal_meeting_url'])
            lst_content.append("**Email:** " + dict_user['email'])

            last_login = date_parser.parse(dict_user['last_login']).strftime("%a, %b %-d, %Y, %-I:%M %p")
            lst_content.append("**Last login:** " + last_login)

            if 'last_client_version' in dict_user:
                lst_content.append("**Last client:** " + dict_user['last_client_version'])

            if dict_user['type'] == 2:
                lic_type = "Licensed"
            else:
                lic_type = "Basic"
            lst_content.append("**Type:** " + lic_type)

            if dict_user['role_id'] == '1':
                role = 'Admin'
            else:
                role = 'Member'
            lst_content.append("**Role:** " + role)

            # Recordings
            if 'recording_stats' in dict_user:
                if dict_user['recording_stats']['total_recordings'] > 0:
                    raw_rec_length = dict_user['recording_stats']['total_recordings_length']
                    if raw_rec_length < 60:
                        recording_length = str(raw_rec_length) + ' minute(s)'
                    else:
                        recording_length = (str(round(dict_user['recording_stats']['total_recordings_length'] / 60, 2))
                                            + " hours")

                    recording_size = self.__format_bytes(dict_user['recording_stats']['total_recordings_size'])

                    # If size of recordings is greater than X GB, we do some markup around it!
                    size_mark_start = ''
                    size_mark_end = ''
                    if int(dict_user['recording_stats']['total_recordings_size']) > (1024 * 1024 * 1024 * 5):
                        size_mark_start = '<span style="background: red; color: white; font-weight: bold"> '
                        size_mark_end = ' </span>'

                    lst_content.append("**Recordings:** " + str(dict_user['recording_stats']['total_recordings']) +
                                       " | " + recording_length +
                                       " | " + size_mark_start + str(round(recording_size[0], 2)) + ' ' + recording_size[1] + size_mark_end)

            lst_content.append("")

        file = "zoom.md"
        return {file: lst_content}

    def _build_content(self):
        md_main = dict()

        # users
        inventory = self.__enumerate_users()
        md_main.update(self.__users_to_markdown(inventory))

        return md_main
