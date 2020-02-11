# coding: utf-8
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
        self.get_token()
        if self.get_channel_info()['online']:
            address = '{}/clips/create'.format(self.apibase)
            data = {'broadcastId': self.config['channel_id'], 'highlightTitle': 'Auto Clip', 'clipDurationInSeconds': 60}
            response = self.request('post', address, headers=self.headers2, data=data)
            if response:
                logger.info(response.json()['contentLocators']['uri'])
            return response
        else:
            logger.warning("Can't create clips when not streaming")
