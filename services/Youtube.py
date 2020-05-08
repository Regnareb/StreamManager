# coding: utf-8
import logging
from common.service import *
logger = logging.getLogger(__name__)

class Main(Service):
    name = 'Youtube'
    scope = "https://www.googleapis.com/auth/youtubepartner https://www.googleapis.com/auth/youtube https://www.googleapis.com/auth/youtube.force-ssl"
    authorization_base_url = "https://accounts.google.com/o/oauth2/v2/auth"
    token_url = "https://oauth2.googleapis.com/token"
    redirect_uri = "http://localhost:60775/"
    apibase = 'https://www.googleapis.com/youtube/v3'
    devurl = 'https://console.developers.google.com/apis/credentials'
    features = {'title': True, 'category': True, 'description': True, 'tags': False, 'clips': False, 'markers': False}

    def get_channel_info(self):
        address = '{}/liveBroadcasts?part=snippet,topicDetails&broadcastType=persistent&mine=true'.format(self.apibase)
        result = self.request('get', address).json()
        address = '{}/videos?part=snippet&id={}'.format(self.apibase, result['items'][0]['id'])
        result2 = self.request('get', address).json()
        name = result2['items'][0]['snippet']['channelTitle']
        categoryId = result2['items'][0]['snippet']['categoryId']
        category = next((cat for cat, catid in self.gamesid.items() if catid == categoryId), '')
        address = '{}/liveBroadcasts?part=snippet&broadcastStatus=active&broadcastType=persistent'.format(self.apibase)
        online = bool(self.request('get', address).json()['items'])
        if online:
            params = {'id': result['items'][0]['id'], 'part': 'liveStreamingDetails'}
            address = '{}/videos'.format(self.apibase)
            viewers = self.request('get', address, params=params).json()
            viewers = viewers['items'][0]['liveStreamingDetails'].get('concurrentViewers', 0)
        else:
            viewers = None
        self.infos = {'online': online, 'title': result['items'][0]['snippet']['title'], 'name': name, 'category': category, 'description': result['items'][0]['snippet']['description'], 'viewers': viewers, 'channel_id': result['items'][0]['id']}
        return self.infos

    def query_category(self, category):
        return self.gamesid

    def validate_category(self, category):
        return bool(self.gamesid.get(category, False))

    def update_channel(self, infos):
        infos = super().update_channel(infos)
        data = {'id': self.config['channel_id'], 'snippet': {}}
        if infos.get('title'):
            data['snippet']['title'] = infos['title']
        else:
            data['snippet']['title'] = self.infos['title']
        if infos.get('description'):
            data['snippet']['description'] = infos['description']
        if infos.get('category'):
            gameid = self.gamesid.get(infos['category'], '')
            if gameid:
                data['snippet']['categoryId'] = gameid
        else:
            data['snippet']['categoryId'] = self.gamesid[self.infos['category']]
        if data.get('snippet'):
            self.get_token()
            address = '{}/videos?part=snippet'.format(self.apibase)
            return self.request('put', address, data=data)

    def get_channel_id(self):
        result = self.get_channel_info()
        self.config['channel_id'] = result['channel_id']

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

    def request(self, action, address, headers=None, data=None, params=None):
        response = super().request(action, address, headers, data, params)
        if response.status_code == '403':
            logger.error("Daily Limits for API calls reached, you won't be able to use that service until midnight Pacific Time.")
        return response
