# coding: utf-8
import time
import logging
import functools
import common.tools as tools
from common.service import *
logger = logging.getLogger(__name__)

# create stream markers
class Main(Service):
    name = 'Twitch'
    scope = "user:edit:broadcast channel_editor clips:edit"
    authorization_base_url = "https://id.twitch.tv/oauth2/authorize"
    token_url = "https://id.twitch.tv/oauth2/token"
    redirect_uri = "http://localhost:60779/"
    apibase = 'https://api.twitch.tv/kraken'
    apibase2 = 'https://api.twitch.tv/helix'
    devurl = 'https://dev.twitch.tv/console/apps'
    features = {'title': True, 'category': True, 'description': False, 'tags': True, 'clips': True, 'markers': True}

    def set_headers(self):
        super().set_headers()
        self.headers['Accept'] = 'application/vnd.twitchtv.v5+json'

    def get_channel_info(self):
        address = '{}/channels/{}'.format(self.apibase, self.config['channel_id'])
        result = self.request('get', address, headers=self.headers).json()
        address = '{}/streams?user_id={}'.format(self.apibase2, self.config['channel_id'])
        online = self.request('get', address, headers=self.headers2).json()['data']
        try:
            viewers = online[0]['viewer_count']
            online = True
        except IndexError:
            viewers = None
            online = False
        self.infos = {'online': online, 'title': result['status'], 'name': result['display_name'], 'category': result['game'], 'description': result['description'], 'viewers': viewers}
        return self.infos

    @functools.lru_cache(maxsize=128)
    def query_category(self, category):
        result = {}
        if category:
            params = {'query': category}
            address = '{}/search/games'.format(self.apibase)
            response = self.request('get', address, headers=self.headers, params=params)
            for i in response.json()['games'] or []:
                result[i['name']] = i['_id']
        return result

    @functools.lru_cache(maxsize=128)
    def validate_category(self, category):
        if category:
            params = {'name': category}
            address = '{}/games'.format(self.apibase2)
            result = self.request('get', address, headers=self.headers2, params=params).json()['data']
            return bool(result)

    def update_channel(self, infos):
        infos = super().update_channel(infos)
        data = {}
        if infos.get('title'):
            data['status'] = infos['title']
        if infos.get('category'):
            data['game'] = infos['category']
        if infos.get('tags'):
            self.update_tags(infos['tags'])
        if data:
            self.get_token()
            data = {'channel': data}
            address = '{}/channels/{}'.format(self.apibase, self.config['channel_id'])
            return self.request('put', address, headers=self.headers, data=data)

    def get_channel_id(self):
        address = '{}/users'.format(self.apibase2)
        result = self.request('get', address, self.headers2).json()
        self.config['channel_id'] = result['data'][0]['id']

    @property
    def alltags(self):
        try:
            return self._alltags
        except AttributeError:
            self._alltags = {}
            cursor = ''
            while cursor is not None:
                address = '{}/tags/streams?first=100&after={}'.format(self.apibase2, cursor)
                response = self.request('get', address, headers=self.headers2).json()
                for i in response['data']:
                    self._alltags[i['localization_names']['en-us']] = i['tag_id']
                cursor = response['pagination'].get('cursor')
            return self._alltags

    def get_tagsid(self, tags):
        tagsid = [v for k,v in self.alltags.items() if k in tags]
        return tagsid

    def update_tags(self, tags):
        if tags:
            self.get_token()
            logger.info('Set tags to: {}'.format(tags))
            tagsid = self.get_tagsid(tags)
            address = '{}/streams/tags?broadcaster_id={}'.format(self.apibase2, self.config['channel_id'])
            data = {'tag_ids': tagsid}
            response = self.request('put', address, headers=self.headers2, data=data)
            if not response:
                logger.error(response.json())
            return response

    @tools.threaded
    def create_clip(self):
        start = time.time()
        self.get_token()
        address = '{}/streams?user_id={}'.format(self.apibase2, self.config['channel_id'])
        response = self.request('get', address, headers=self.headers2)
        online = response.json()['data']
        if online:
            if self.config['delay']:
                elapsed = time.time() - start
                delay = int(self.config['delay']) - elapsed
                time.sleep(max(0, delay))
            address = '{}/clips?broadcaster_id={}'.format(self.apibase2, self.config['channel_id'])
            response = self.request('post', address, headers=self.headers2)
            time.sleep(15)
            address = '{}/clips?id={}'.format(self.apibase2, response.json()['data'][0]['id'])
            response2 = self.request('get', address, headers=self.headers2)
            if response2.json()['data']:
                logger.log(777, 'Your Twitch Clip has been created at this URL: {}'.format(response2.json()['data'][0]['url']))
            else:
                logger.error("Couldn't seem to create the clip.")
            return response
        else:
            logger.error("Can't create a clip if you are not streaming.")

    @tools.threaded
    def create_marker(self):
        start = time.time()
        self.get_token()
        address = '{}/streams?user_id={}'.format(self.apibase2, self.config['channel_id'])
        response = self.request('get', address, headers=self.headers2)
        online = response.json()['data']
        if online:
            if self.config['delay']:
                elapsed = time.time() - start
                delay = int(self.config['delay']) - elapsed
                time.sleep(max(0, delay))
            params = {'user_id': self.config['channel_id'], 'description': 'Created automatically with StreamManager'}
            address = '{}/streams/markers'.format(self.apibase2)
            response = self.request('post', address, headers=self.headers2, params=params)
            if response.json()['data']:
                logger.log(777, 'Your Twitch Marker has been created: {} - {}'.format(response.json()['data'][0]['id'], response.json()['data'][0]['created_at']))
            else:
                logger.error("Couldn't seem to create the marker.")
            return response
        else:
            logger.error("Can't create a marker if you are not streaming.")
