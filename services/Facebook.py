# coding: utf-8
import logging
from common.service import *
logger = logging.getLogger(__name__)

class Main(Service):
    name = 'Facebook'
    scope = "user_videos publish_video"
    authorization_base_url = "https://www.facebook.com/dialog/oauth"
    token_url = "https://graph.facebook.com/oauth/access_token"
    redirect_uri = "http://localhost:60776/"
    apibase = 'https://graph.facebook.com/v5.0'
    devurl = 'https://developers.facebook.com/apps/'
    features = {'title': True, 'category': False, 'description': True, 'tags': False, 'clips': False}

    def get_channel_id(self):
        address = '{}/me?fields=id'.format(self.apibase)
        result = self.request('get', address).json()
        self.config['channel_id'] = result['id']

    def get_channel_info(self):
        address = '{}/{}'.format(self.apibase, self.video_id)
        result = self.request('get', address).json()
        online = True if result['status'] == 'LIVE' else False
        self.infos = {'online': online, 'title': result['title'], 'name': '', 'category': '', 'description': ''}

    @property
    def video_id(self):
        address = '{}/{}/live_videos?fields=live_views,status,ingest_streams'.format(self.apibase, self.config['channel_id'])
        result = self.request('get', address).json()['data'][0]
        return result['id']

    def update_channel(self, infos):
        infos = super().update_channel(infos)
        data = {}
        if infos['title']:
            data['title'] = infos['title']
        if infos['description']:
            data['description'] = infos['description']
        if data:
            self.get_token()
            address = '{}/{}'.format(self.apibase, self.video_id)
            return self.request('post', address, data=data)
