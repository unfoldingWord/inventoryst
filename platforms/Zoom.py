from .Platform import Platform
import base64
import requests
from dateutil import parser as date_parser, relativedelta
import datetime
import pprint
import time

# https://marketplace.zoom.us/develop/apps/
# https://developers.zoom.us/docs/api/


class Zoom(Platform):
    def __init__(self):
        super().__init__()

        self.__config = self.load_config('zoom')

        self.access_token = self.__request_access_token()

        self.__headers = [
            ['Authorization', 'Bearer ' + self.access_token],
            ['Content-Type', 'application/x-www-form-urlencoded'],
        ]

    def __request_access_token(self):
        account_id = self.__config['account_id']
        client_id = self.__config['client_id']
        client_secret = self.__config['client_secret']

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

    def __get_recording_stats(self, user_id, start_date):
        # As of my current knowledge, there is no way to know if a user even has recordings or not.
        # We can only request recordings per user, even more limited by the fact that we can only
        # request recordings over a period of maximum a month.
        # This forces us to iterate, per user, over all the months that recordings could have taken place
        # Therefore, this is a very expensive operation. We have been able to tame it a bit by
        # using the creation_date of a user as the start date for searching, as a user can only create recordings
        # when they themselves have been created.

        # Recordings can only be fetched per month, so we need to query multiple times
        start_date = date_parser.parse(start_date).date()
        end_date = datetime.date.today()

        range_months = self.__month_range(start_date, end_date)

        total_recording_number = 0
        total_recording_size = 0
        total_recording_length = 0

        for start_date in range_months:
            end_date = range_months[start_date]
            api_url = f'https://api.zoom.us/v2/users/{user_id}/recordings?from={start_date}&to={end_date}?page_size=300'

            recordings = self._get_json_from_url(api_url, self.__headers)
            if recordings['total_records'] > 0:
                # pprint.pprint(recordings)

                total_recording_number += recordings['total_records']

                for recording in recordings['meetings']:
                    total_recording_length += recording['duration']

                    for file in recording['recording_files']:
                        total_recording_size += file['file_size']

            # We are getting errors of 'Remote end closed connection without response'
            # As this might have to do with us overheating the system, we are building in sleep time
            # This is a shot in the dark, though...
            time.sleep(1)

        dict_recording_stats = {
            'total_recordings': total_recording_number,
            'total_recordings_size': total_recording_size,
            'total_recordings_length': total_recording_length
        }

        return dict_recording_stats

    def __enumerate_rooms(self):
        dict_rooms = dict()
        dict_rooms["meta"] = dict()
        dict_rooms["content"] = list()

        rooms = self._get_json_from_url('https://api.zoom.us/v2/rooms?page_size=100', self.__headers)
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

        # Get plan usage
        url_usage = 'https://api.zoom.us/v2/accounts/me/plans/usage?page_size=100'
        dict_plan_usage = self._get_json_from_url(url_usage, self.__headers)

        url_users = 'https://api.zoom.us/v2/users?page_size=100'
        users = self._get_json_from_url(url_users, self.__headers)

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

            url_user = f'https://api.zoom.us/v2/users/{user['id']}'
            dict_additional_user_data = self._get_json_from_url(url_user, self.__headers)

            field_filter = ['id', 'first_name', 'last_name', 'display_name', 'email', 'pmi', 'last_client_version',
                            'last_login_time', 'verified', 'type', 'role_id', 'pic_url', 'user_created_at']

            tmp_user = self._filter_fields(user, field_filter)

            tmp_user['full_name'] = user['first_name'] + ' ' + user['last_name']
            tmp_user['personal_meeting_url'] = dict_additional_user_data['personal_meeting_url']

            # Recordings statistics
            # On development, we only try to fetch recordings for a few users,
            # as this is an expensive (time-wise) operation
            if rec_fetch_limit < 3:
                recordings = self.__get_recording_stats(user['id'], user['user_created_at'])
                tmp_user['recording_stats'] = recordings
                if self._stage == 'dev':
                    rec_fetch_limit += 1

            dict_users['content'].append(tmp_user)

        return dict_users

    def __users_to_markdown(self, inventory):

        lst_content = list()

        lst_content.append(">[!info] General information")

        # Users
        lst_content.append(self._item(self._link('https://us02web.zoom.us/account/user#', 'Users total'),
                                      inventory["meta"]["user_count"]))
        lst_content.append(self._item('Owners', inventory["meta"]["owner_count"]))
        lst_content.append(self._item('Admins', inventory["meta"]["admin_count"]))
        lst_content.append(self._item('Members', inventory["meta"]["member_count"]))
        lst_content.append('>\n>---')

        # Licenses
        lst_content.append(self._item(self._link('https://admin.zoom.us/billing', 'Licenses'),
                                      inventory["meta"]["licenses_available"]))
        lst_content.append(self._item('Licenses uesd', inventory["meta"]["licenses_used"]))
        lst_content.append('>\n>---')

        # Recordings
        lst_content.append(self._item(self._link('https://admin.zoom.us/recording/management', 'Recording storage'),
                                      inventory["meta"]["recording_storage"]))
        lst_content.append(self._item('Recording storage used', inventory["meta"]["recording_storage_used"]))
        lst_content.append("")

        # All the users
        lst_users = sorted(inventory["content"], key=lambda item: item["full_name"])
        for dict_user in lst_users:
            avatar_style = {'width': '75px', 'height': '75px'}
            if 'pic_url' in dict_user:
                avatar = self._avatar(dict_user['pic_url'], avatar_type='image', style_overrides=avatar_style)
            else:
                avatar = self._avatar(self._pull_initials(dict_user['full_name']), avatar_type='text', style_overrides=avatar_style)

            if dict_user['full_name'] == dict_user['display_name']:
                display_name = dict_user['full_name']
            else:
                display_name = dict_user['full_name'] + " (" + dict_user['display_name'] + ")"

            lst_content.append(f'{avatar}{self._item('Name', display_name)}')
            lst_content.append(self._item('Created', self._format_date(dict_user['user_created_at'])))

            lst_content.append(self._item('PMI', dict_user['pmi']))
            lst_content.append(self._item('Personal meeting URL', dict_user['personal_meeting_url']))
            lst_content.append(self._item('Email', dict_user['email']))

            lst_content.append(self._item('Last login', self._format_date(dict_user['last_login_time'])))

            if 'last_client_version' in dict_user:
                lst_content.append(self._item('Last client', dict_user['last_client_version']))

            if dict_user['type'] == 2:
                lic_type = "Licensed"
            else:
                lic_type = "Basic"
            lst_content.append(self._item('Type', lic_type))

            if dict_user['role_id'] == '1':
                role = 'Admin'
            else:
                role = 'Member'
            lst_content.append(self._item('Role', role))

            # Recordings
            if 'recording_stats' in dict_user:
                if dict_user['recording_stats']['total_recordings'] > 0:
                    raw_rec_length = dict_user['recording_stats']['total_recordings_length']
                    if raw_rec_length < 60:
                        recording_length = str(raw_rec_length) + ' minute(s)'
                    else:
                        recording_length = (str(round(dict_user['recording_stats']['total_recordings_length'] / 60, 2))
                                            + " hours")

                    recording_size = self._format_bytes(dict_user['recording_stats']['total_recordings_size'])

                    # If size of recordings is greater than X GB, we make it a warning
                    recording_warning_size = self.__config['recording_warning_size']
                    recording_size_display = recording_size
                    if int(dict_user['recording_stats']['total_recordings_size']) > (1024 * 1024 * 1024 * recording_warning_size):
                        recording_size_display = self._highlight(recording_size, 'white', 'red')

                    lst_content.append(self._item('Recordings', str(dict_user['recording_stats']['total_recordings']) +
                                       " | " + recording_length +
                                       " | " + recording_size_display))

            lst_content.append("")

        file = "zoom.md"
        return {file: lst_content}

    def _build_content(self):
        md_main = dict()

        # users
        inventory = self.__enumerate_users()
        md_main.update(self.__users_to_markdown(inventory))

        return md_main
