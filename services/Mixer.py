# coding: utf-8
import time
import logging
import functools
from common.service import *
logger = logging.getLogger(__name__)

class Main(Service):
    name = 'Mixer'
    scope = "channel:update:self channel:clip:create:self"
    authorization_base_url = "https://mixer.com/oauth/authorize"
    token_url = "https://mixer.com/api/v1/oauth/token"
    redirect_uri = "http://localhost:60778/"
    apibase = 'https://mixer.com/api/v1'
    devurl = 'https://mixer.com/lab/oauth'
    features = {'title': True, 'category': True, 'description': False, 'tags': False, 'clips': True}

    def get_channel_info(self):
        address = '{}/channels/{}'.format(self.apibase, self.config['channel_id'])
        result = self.request('get', address).json()
        viewers = result['viewersCurrent'] if result['online'] else None
        self.infos = {'online': result['online'], 'title': result['name'], 'name': result['token'], 'category': result['type']['name'], 'description': result['description'], 'viewers': viewers, 'viewersTotal': result['viewersTotal']}
        return result

    def update_channel(self, infos):
        infos = super().update_channel(infos)
        data = {}
        if infos['title']:
            data['name'] = infos['title']
        if infos['category']:
            data['typeId'] = self.get_game_id(infos['category'])
        if data:
            address = '{}/channels/{}'.format(self.apibase, self.config['channel_id'])
            return self.request('patch', address, data=data)

    def get_channel_id(self):
        address = '{}/users/current'.format(self.apibase)
        self.config['channel_id'] = self.request('get', address).json()['channel']['id']

    @functools.lru_cache(maxsize=128)
    def query_category(self, category):
        params = {'query': 'eq:'+category}
        address = '{}/types'.format(self.apibase)
        response = self.request('get', address, params=params)
        result = {}
        for i in response.json():
            result[i['name']] = i['id']
        return result

    def get_game_id(self, category):
        if category:
            categories = self.query_category(category)
            for k, v in categories.items():
                if k == category:
                    return v

    def validate_category(self, category):
        return bool(self.get_game_id(category))

    def create_clip(self):
        start = time.time()
        self.get_token()
        if self.get_channel_info()['online']:
            address = '{}/broadcasts/current'.format(self.apibase)
            response = self.request('get', address, headers=self.headers2)
            broadcastId = response.json()['id']
            if self.config['delay']:
                elapsed = time.time() - start
                time.sleep(int(self.config['delay']) - elapsed)
            address = '{}/clips/create'.format(self.apibase)
            data = {'broadcastId': broadcastId, 'highlightTitle': 'Auto Clip', 'clipDurationInSeconds': 60}
            response = self.request('post', address, headers=self.headers2, data=data)
            if response:
                logger.log(777, 'Your Twitch Clip has been created at this URL: {}'.format(response.json()['contentLocators']['uri']))
            elif response.json().get('errorCode', None) == 25206:
                logger.error('You need to be a Verified channel or Mixer Partner to be able to create clips: https://mixer.com/dashboard/onboarding/verified')
            return response
        else:
            logger.error("Can't create clips when not streaming")

    def request(self, action, address, headers=None, data=None, params=None):
        response = super().request(action, address, headers, data, params)
        if response.status_code == '469':
            logger.error("Daily Limits for API calls reached, you won't be able to use that service until midnight Pacific Time.")
        return response
