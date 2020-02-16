# coding: utf-8
import logging
import functools
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

    @functools.lru_cache(maxsize=128)
    def query_category(self, category):
        address = '{}/search?type=adinterest&q={}'.format(self.apibase, category)
        response = self.request('get', address)
        result = {}
        for i in response.json()['data']:
            result[i['name']] = i['id']
        return result

    def validate_category(self, category):
        return bool(self.query_category(category).get(category, False))

    def get_channel_id(self):
        address = '{}/me?fields=id'.format(self.apibase)
        result = self.request('get', address).json()
        self.config['channel_id'] = result['id']

    def get_channel_info(self):
        params = {'fields': 'live_views,title,status'}
        address = '{}/{}'.format(self.apibase, self.video_id)
        result = self.request('get', address, params=params).json()
        online = True if result['status'] == 'LIVE' else False
        viewers = result['live_views'] if online else None
        self.infos = {'online': online, 'title': result['title'], 'name': '', 'category': '', 'description': '', 'viewers': viewers}

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
        if infos['category']:
            idtag = self.query_category(infos['category']).get(infos['category'])
            if idtag:
                data['content_tags'] = idtag
        if data:
            self.get_token()
            address = '{}/{}'.format(self.apibase, self.video_id)
            return self.request('post', address, data=data)
