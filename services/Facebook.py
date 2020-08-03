# coding: utf-8
import logging
import functools
import common.tools as tools
from common.service import *
logger = logging.getLogger(__name__)

@tools.decorate_all_methods(tools.catch_exception(logger=logger))
class Main(Service):
    name = 'Facebook'
    scope = "user_videos publish_video"
    authorization_base_url = "https://www.facebook.com/dialog/oauth"
    token_url = "https://graph.facebook.com/oauth/access_token"
    redirect_uri = "http://localhost:60776/"
    apibase = 'https://graph.facebook.com/v5.0'
    devurl = 'https://developers.facebook.com/apps/'
    features = {'title': True, 'category': False, 'tags': False, 'clips': False, 'markers': False}

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
        self.infos = {'online': online, 'title': result['title'], 'name': '', 'category': '', 'viewers': viewers}
        return self.infos

    @property
    def video_id(self):
        try:
            address = '{}/{}/live_videos?fields=live_views,status,ingest_streams'.format(self.apibase, self.config['channel_id'])
            result = self.request('get', address).json()['data'][0]
        except:
            logger.warning('There are no live video created. Creating one')
            address = '{}/{}/live_videos?status=LIVE_NOW'.format(self.apibase, self.config['channel_id'])
            result = self.request('post', address).json()
        return result['id']

    def update_channel(self, infos):
        infos = super().update_channel(infos)
        data = {}
        if infos.get('title'):
            data['title'] = infos['title']
        if infos.get('category'):
            idtag = self.query_category(infos['category']).get(infos['category'])
            if idtag:
                data['content_tags'] = idtag
        if data:
            self.get_token()
            address = '{}/{}'.format(self.apibase, self.video_id)
            return self.request('post', address, data=data)
