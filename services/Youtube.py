# coding: utf-8
import logging
from common.service import *
logger = logging.getLogger(__name__)

class Main(Service):
    name = 'Youtube'
    scope = "https://www.googleapis.com/auth/youtubepartner https://www.googleapis.com/auth/youtube https://www.googleapis.com/auth/youtube.force-ssl"
    authorization_base_url = "https://accounts.google.com/o/oauth2/v2/auth"
    token_url = "https://oauth2.googleapis.com/token"
    redirect_uri = "http://localhost:778/"
    apibase = 'https://www.googleapis.com/youtube/v3'
    features = {'title': True, 'description': True, 'category': True, 'tags': False, 'clips': False}

    def get_channel_info(self):
        address = '{}/liveBroadcasts?part=snippet&broadcastType=persistent&mine=true'.format(self.apibase)
        result = self.request('get', address).json()
        address = '{}/channels?part=snippet&mine=true'.format(self.apibase)
        name = self.request('get', address).json()['items'][0]['snippet']['title']
        address = '{}/liveBroadcasts?part=snippet&broadcastStatus=active&broadcastType=persistent'.format(self.apibase)
        online = bool(self.request('get', address).json()['items'])
        self.infos = {'online': online, 'title': result['items'][0]['snippet']['title'], 'name': name, 'category': '', 'description': result['items'][0]['snippet']['description']}
        return result

    def query_category(self, category):
        return self.gamesid

    def validate_category(self, category):
        return bool(self.gamesid.get(category, False))

    def update_channel(self, infos):
        infos = super().update_channel(infos)
        data = {'id': self.config['channel_id'], 'snippet': {}}
        if infos['title']:
            data['snippet']['title'] = infos['title']
        if infos['description']:
            data['snippet']['description'] = infos['description']
        if infos['category']:
            gameid = self.gamesid.get(infos['category'], '')
            if gameid:
                data['snippet']['categoryId'] = gameid
        if data['snippet']:
            self.get_token()
            address = '{}/videos?part=snippet'.format(self.apibase)
            return self.request('put', address, data=data)

    def get_channel_id(self):
        result = self.get_channel_info()
        self.config['channel_id'] = result['items'][0]['id']

    @property
    def gamesid(self):
        try:
            return self._gamesid
        except AttributeError:
            self._gamesid = {}
            address = '{}/videoCategories?part=snippet&regionCode=us'.format(self.apibase)
            response = self.request('get', address)
            for i in response.json()['items']:
                self._gamesid[i['snippet']['title']] = i['id']
            return self._gamesid

    def create_clip(self):
        pass  # Not supported yet
