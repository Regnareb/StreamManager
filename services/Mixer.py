# coding: utf-8
import logging
from common.service import *
logger = logging.getLogger(__name__)

class Main(Service):
    name = 'Mixer'
    scope = "channel:update:self channel:clip:create:self"
    client_id = "e1902ca98fbf96b908dd9002727f56ae4578fb0c10052cdf"
    client_secret = "49172d24929486942577f0e7e23acce884f03c2801cf1222077f145599e17a71"
    authorization_base_url = "https://mixer.com/oauth/authorize"
    token_url = "https://mixer.com/api/v1/oauth/token"
    redirect_uri = "http://localhost:777/"
    apibase = 'https://mixer.com/api/v1'
    features = {'title': True, 'description': False, 'category': True, 'tags': False, 'clips': True}

    def get_channel_info(self):
        address = '/{}channels/{}'.format(self.apibase, self.config['channel_id'])
        return self.request('get', address).json()

    def update_channel(self, infos):
        infos = super().update_channel(infos)
        data = {}
        if infos['title']:
            data['name'] = infos['title']
        if infos['category']:
            category = self.config.get('assignation', {}).get(infos['category'], infos['category'])
            data['typeId'] = self.get_game_id(category)
        if data:
            self.get_token()
            address = '{}/channels/{}'.format(self.apibase, self.config['channel_id'])
            return self.request('patch', address, data=data)

    def get_channel_id(self):
        address = '{}/users/current'.format(self.apibase)
        self.config['channel_id'] = self.request('get', address).json()['channel']['id']

    def get_game_id(self, game):
        address = '{}/types?&query=eq:{}'.format(self.apibase, game)
        response = self.request('get', address)
        for i in response.json():
            if i['name'] == game:
                return i['id']

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
