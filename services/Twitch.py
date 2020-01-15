# coding: utf-8
import time
import logging
import common.tools as tools
from common.service import *
logger = logging.getLogger(__name__)

# create stream markers
class Main(Service):
    name = 'Twitch'
    scope = "user:edit:broadcast channel_editor clips:edit"
    client_id = "l4b52ea1o7d2hpmyezyyflq0ya1rrr"
    client_secret = "hg751cb5qzwsjwdfw0ggr2n30p7e0s"
    authorization_base_url = "https://id.twitch.tv/oauth2/authorize"
    token_url = "https://id.twitch.tv/oauth2/token"
    redirect_uri = "http://localhost:776/"
    apibase = 'https://api.twitch.tv/kraken'
    apibase2 = 'https://api.twitch.tv/helix'
    features = {'title': True, 'description': False, 'category': True, 'tags': True, 'clips': True}

    def set_headers(self):
        super().set_headers()
        self.headers['Accept'] = 'application/vnd.twitchtv.v5+json'

    def get_channel_info(self):
        address = '{}/channels/{}'.format(self.apibase, self.config['channel_id'])
        result = self.request('get', address).json()
        address = '{}/streams?user_id={}'.format(self.apibase2, self.config['channel_id'])
        online = self.request('get', address).json()['data']
        self.infos = {'online': bool(online), 'title': result['status'], 'name': result['display_name'], 'category': result['game'], 'description': result['description']}
        return result

    def query_category(self, category):
        if category:
            params = {'query': category}
            address = '{}/search/games'.format(self.apibase)
            response = self.request('get', address, params=params)
            result = {}
            for i in response.json()['games'] or []:
                result[i['name']] = i['_id']
            return result

    def validate_category(self, category):
        if category:
            params = {'name': category}
            address = '{}/games'.format(self.apibase2)
            result = self.request('get', address, params=params).json()['data']
            return bool(result)

    def update_channel(self, infos):
        infos = super().update_channel(infos)
        data = {}
        if infos['title']:
            data['status'] = infos['title']
        if infos['category']:
            data['game'] = self.config.get('assignation', {}).get(infos['category'], infos['category'])
        self.update_tags(infos['tags'])
        if data:
            self.get_token()
            data = {'channel': data}
            address = '{}/channels/{}'.format(self.apibase, self.config['channel_id'])
            return self.request('put', address, data=data)

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
                response = self.request('get', address).json()
                for i in response['data']:
                    self._alltags[i['localization_names'][self.config['localisation']]] = i['tag_id']
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
        self.get_token()
        address = '{}/streams?user_id={}'.format(self.apibase2, self.config['channel_id'])
        response = self.request('get', address)
        online = response.json()['data']
        if online:
            address = '{}/clips?broadcaster_id={}'.format(self.apibase2, self.config['channel_id'])
            response = self.request('post', address, headers=self.headers2)
            for _ in range(15):  # Check if the clip has been created
                address = '{}/clips?id={}'.format(self.apibase2, response.json()['data'][0]['id'])
                response2 = self.request('get', address)
                if response2.json()['data']:
                    logger.info(response2.json()['data'][0]['url'])
                    break
                time.sleep(1)
            else:
                logger.error("Couldn't seem to create the clip.")
            return response
        else:
            logger.error("Can't create a clip if you are not streaming.")
