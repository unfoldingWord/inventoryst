
from .Platform import Platform
import zulip
from datetime import datetime
from pprint import pp

class Zulip(Platform):
  def __init__(self):
    super().__init__()

    self.__config = self.load_config('zulip')
    self.__api_client = zulip.Client(email=self.__config['email'],
                                     api_key=self.__config['api_key'],
                                     site=self.__config['site'])
    self._inc_api_call()

    self.__auth = (self.__config['email'], self.__config['api_key'])

  def __enumerate_members(self, active=None, bots=False):
    dict_members = dict()
    dict_members['meta'] = dict()
    dict_members['content'] = list()

    members = self.__api_client.get_members()
    self._inc_api_call()

    field_filter = ['user_id', 'email', 'delivery_email', 'is_active', 'is_bot', 'bot_owner_id', 'role', 'is_owner', 'full_name',
                    'date_joined', 'avatar_url', 'time_zone']

    dict_members['meta']['user_count'] = 0
    dict_members['meta']['active_count'] = 0
    dict_members['meta']['member_count'] = 0
    dict_members['meta']['owner_count'] = 0
    dict_members['meta']['admin_count'] = 0
    dict_members['meta']['moderator_count'] = 0
    dict_members['meta']['guest_count'] = 0

    last_presence = {}
    if active is True:
      last_presence = self.__api_client.get_realm_presence()['presences']
      self._inc_api_call()

    for user in members['members']:
      if bots:
        if user['is_bot'] is False:
          continue
      else:
        # I don't want bots
        if user['is_bot'] is True:
          continue
        # Filter on active
        if user['is_active'] is not active:
          continue

      dict_members['meta']['user_count'] += 1
      dict_members['meta']['active_count'] += 1 if user['is_active'] is True else 0
      dict_members['meta']['admin_count'] += 1 if user['role'] == 200 else 0
      dict_members['meta']['owner_count'] += 1 if user['is_owner'] is True else 0
      dict_members['meta']['member_count'] += 1 if user['role'] == 400 else 0
      dict_members['meta']['guest_count'] += 1 if user['is_guest'] is True else 0
      dict_members['meta']['moderator_count'] += 1 if user['role'] == 300 else 0

      # Filter fields
      user = self._filter_fields(user, field_filter)

      # For activated users, we want to see if they are really active,
      # so we fetch their latest message
      if active is True:
        # Checking for presence
        if user['email'] in last_presence:
          user['presence'] = last_presence[user['email']]['aggregated']['timestamp']

        # Checking last message
        result = self.__api_client.get_messages({
          'anchor': 'newest',
          'num_before': 1,
          'num_after': 0,
          'narrow': [{'operator': 'sender', 'operand': user['email']}]
        })

        latest_message = result['messages'][0] if 'messages' in result and result['messages'] else None
        if latest_message:
          user['last_message_sent'] = latest_message['timestamp']
        else:
          user['last_message_sent'] = None

      # For bots, we want to know the owner
      if bots is True:
        if user['bot_owner_id'] is not None:
          owner = self.__api_client.get_user_by_id(user['bot_owner_id'])
          self._inc_api_call()

          user['bot_owner'] = owner['user']['full_name']

        else:
          user['bot_owner'] = 'No owner'

      dict_members['content'].append(user)

    return dict_members

  def __enumerate_channels(self):
    dict_return = dict()
    dict_return['meta'] = dict()
    dict_return['content'] = list()

    channels = self.__api_client.get_streams(include_all=True)
    self._inc_api_call()

    field_filter = ['stream_id', 'name', 'is_archived', 'creator_id', 'date_created', 'description', 'invite_only',
                    'is_web_public', 'is_recently_active', 'subscriber_count', 'stream_id']

    dict_return['meta']['channel_count'] = 0
    dict_return['meta']['active_count'] = 0
    dict_return['meta']['private_count'] = 0

    channels_sorted = sorted(channels['streams'], key=lambda item: item["name"].lower())
    for channel in channels_sorted:

      dict_return['meta']['channel_count'] += 1
      dict_return['meta']['active_count'] += 1 if channel['is_archived'] is False else 0
      dict_return['meta']['private_count'] += 1 if channel['invite_only'] is True else 0

      # Main fields
      channel = self._filter_fields(channel, field_filter)

      # Creator
      if 'creator_id' in channel and channel['creator_id']:
        creator = self.__api_client.get_user_by_id(channel['creator_id'])
        self._inc_api_call()

        channel['creator'] = 'Unknown'
        if 'user' in creator:
          channel['creator'] = creator['user']['full_name']

      # Subscribers
      sub_url = f'{self.__config['site']}/api/v1/streams/{channel['stream_id']}/members'
      sub_ids = self._get_json_from_url(sub_url, auth=self.__auth)
      if 'subscribers' in sub_ids:
        subscriber_ids = sub_ids['subscribers']

        members = self.__api_client.get_members(request={'user_ids': subscriber_ids})
        self._inc_api_call()

        subscribers = 'Unknown'
        if 'members' in members:
          subscribers = [subscriber['full_name'] for subscriber in members['members']]

        channel['subscribers'] = subscribers

      # Topics
      topics = self.__api_client.get_stream_topics(channel['stream_id'])

      if 'topics' in topics:
        topic_count = len(topics['topics'])
      else:
        topic_count = '-' # Probably no access to this channel, so we don't know.

      channel['topic_count'] = topic_count

      # Add to return
      dict_return['content'].append(channel)

    return dict_return

  def __enumerate_user_groups(self):
    dict_return = dict()
    dict_return['meta'] = dict()
    dict_return['content'] = list()

    # This endpoint is only available to members and administrators; bots and guests cannot use this endpoint.
    groups = self.__api_client.get_user_groups()
    self._inc_api_call()

    field_filter = ['name', 'date_created', 'description', 'members', 'deactivated']

    group_count = 0
    active_count = 0
    for group in groups['user_groups']:
      group_count += 1
      active_count += 1 if group['deactivated'] is False else 0

      group = self._filter_fields(group, field_filter)

      members = [member['full_name'] for member in self.__api_client.get_members(request={'user_ids': group['members']})['members']]
      self._inc_api_call()
      group['members'] = members

      dict_return['content'].append(group)

    dict_return['meta']['group_count'] = group_count
    dict_return['meta']['active_count'] = active_count

    return dict_return

  def __markdown_channels(self, dict_channels):
    lst_content = list()

    lst_content.append(">[!info] General information")
    lst_content.append(self._item(f'Channels', f"{dict_channels['meta']['channel_count']}"))
    lst_content.append(self._item(f'Active', f"{dict_channels['meta']['active_count']}"))
    lst_content.append(self._item(f'Private', f"{dict_channels['meta']['private_count']}"))
    lst_content.append('')

    for channel in dict_channels['content']:
      lst_labels = [
        self._highlight('Archived', color='gray', border_color='gray') if channel['is_archived'] else '',
        self._highlight('Private', color='gray', border_color='gray') if channel['invite_only'] else '',
        self._highlight('Stale', color='gray', border_color='gray') if channel['is_recently_active'] is False else '',
        self._highlight('Public', color='white', background='red') if channel['is_web_public'] else ''
      ]

      lst_content.append(f'{self._header(channel['name'], 3)} {' '.join(lst_labels)}')
      lst_content.append(self._note(channel['description'] if channel['description'] else 'No description'))
      lst_content.append(self._item('Created', self._format_date(channel['date_created'])))
      lst_content.append(self._item('Creator', channel['creator'] if 'creator' in channel else 'Unknown'))
      lst_content.append(self._item('Recently active', 'yes' if channel['is_recently_active'] else 'no'))
      lst_content.append(self._item('Topic count', channel['topic_count']))
      lst_content.append(self._item('Subscriber count', channel['subscriber_count']))

      if 'subscribers' in channel:
        lst_content.append(self._item('Subscribers', ', '.join(channel['subscribers'])))

    file = 'zulip/channels.md'
    return {file: lst_content}

  def __markdown_groups(self, dict_groups):
    lst_content = list()

    lst_content.append(">[!info] General information")
    lst_content.append(self._item(f'Groups', f"{dict_groups['meta']['group_count']}"))
    lst_content.append(self._item(f'Active', f"{dict_groups['meta']['active_count']}"))
    lst_content.append('')

    for group in dict_groups['content']:
      label_inactive = self._highlight('Deactivated', color='gray', border_color='gray') if group['deactivated'] else ''

      lst_content.append(f'{self._header(group['name'], 3)} {label_inactive}')
      lst_content.append(self._note(group['description']))
      lst_content.append(self._item('Created', self._format_date(group['date_created'])))
      lst_content.append(self._item('Members', ', '.join(group['members'])))

    file = 'zulip/groups.md'
    return {file: lst_content}

  def __markdown_members(self, dict_users, active=None, bots=False):
    lst_content = list()

    # General info box
    lst_content.append(">[!info] General information")
    count_type = 'bots' if bots is True else 'users'
    lst_content.append(self._item(f'Total number of {count_type}', f"{dict_users['meta']['user_count']}"))
    if bots is True:
      lst_content.append(self._item('Active bots', dict_users['meta']['active_count']))
    if active is True:
      lst_content.append(self._item('Owners', dict_users['meta']['owner_count']))
      lst_content.append(self._item('Admins', dict_users['meta']['admin_count']))
      lst_content.append(self._item('Moderators', dict_users['meta']['moderator_count']))
      lst_content.append(self._item('Members', dict_users['meta']['member_count']))
      lst_content.append(self._item('Guests', dict_users['meta']['guest_count']))
    lst_content.append('')

    role_to_title = {
      100: 'Owner',
      200: 'Administrator',
      300: 'Moderator',
      400: 'Member',
      600: 'Guest'
    }

    users_sorted = sorted(dict_users['content'], key=lambda item: item["full_name"])
    for user in users_sorted:

      # Avatar
      if user['avatar_url'] is not None:
        avatar = self._avatar(user['avatar_url'])
      else:
        avatar = self._avatar(self._pull_initials(user['full_name']), avatar_type='text')

      # Deactivated
      label_deactivated = self._highlight('Deactivated', 'gray', border_color='gray') if user['is_active'] is False else ''

      # Bots
      label_bot = self._highlight('Bot', 'gray', border_color='gray') if user['is_bot'] is True else ''

      # Activity: Mark inactive when not logged in or not sent a message for a certain period
      label_activity = ''
      inactive_day_limit = self.__config['user']['inactive_days']
      date_last_active = None
      if 'presence' in user and user['presence']:
        date_last_active = datetime.fromtimestamp(user['presence'])
      elif 'last_message_sent' in user and user['last_message_sent']:
        date_last_active = datetime.fromtimestamp(user['last_message_sent'])

      # If we have a date last active, we can do a label
      if date_last_active:
        delta = datetime.today() - date_last_active

        if delta.days >= inactive_day_limit:
          label_activity = self._highlight(f'Inactive ({delta.days} days)', color='gray', border_color='gray')

      lst_content.append(f"{avatar}**{user['full_name']}** {label_bot} {label_deactivated} {label_activity}")

      lst_content.append(self._item('Email', user['delivery_email']))
      if user['is_bot'] is True:
          lst_content.append(self._item('Bot owner', user['bot_owner']))

      lst_content.append(self._item('Role', role_to_title[user['role']]))
      lst_content.append(self._item('Date joined', self._format_date(user['date_joined'])))

      # Only for active, non-bot users
      if active is True and bots is False:
        # Presence
        if 'presence' in user and user['presence']:
          presence = self._format_date(user['presence'])
        else:
          presence = self._highlight('Unknown', 'white', background='orange')
        lst_content.append(self._item('Last seen', presence))

        # Last message sent
        if 'last_message_sent' in user and user['last_message_sent']:
          last_message_sent = self._format_date(user['last_message_sent'])
        else:
          last_message_sent = self._highlight('Unknown', 'white', background='orange')
        lst_content.append(self._item('Last message sent', last_message_sent))

      lst_content.append('')

    if bots:
      file = "zulip/bots.md"
    else:
      if active is True:
        file = "zulip/active_users.md"
      else:
        file = "zulip/deactivated_users.md"
    return {file: lst_content}

  def _build_content(self):
    md_main = dict()

    # # Active users
    members = self.__enumerate_members(active=True)
    md_main.update(self.__markdown_members(members, active=True))

    # Deactivated users
    members = self.__enumerate_members(active=False)
    md_main.update(self.__markdown_members(members, active=False))

    # Bots
    bots = self.__enumerate_members(bots=True)
    md_main.update(self.__markdown_members(bots, bots=True))

    groups = self.__enumerate_user_groups()
    md_main.update(self.__markdown_groups(groups))

    channels = self.__enumerate_channels()
    md_main.update(self.__markdown_channels(channels))

    return md_main