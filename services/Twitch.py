# coding: utf-8
import time
import logging
import tools
from service import *
logger = logging.getLogger(__name__)





class Main(Service):
    name = 'Twitch'
    apibase = 'https://api.twitch.tv/kraken'
    apibase2 = 'https://api.twitch.tv/helix'
    features = {'title': True, 'description': False, 'category': True, 'tags': True}

    def set_headers(self):
        super().set_headers()
        self.headers['Accept'] = 'application/vnd.twitchtv.v5+json'

    def get_channel_info(self):
        address = '{}/channels/{}'.format(self.apibase, self.config['channel_id'])
        return self.request('get', address).json()

    def update_channel(self, infos):
        infos = super().update_channel(infos)
        data = {}
        channel_info = self.get_channel_info()
        if infos['title']:
            data['status'] = infos['title'] or channel_info['status']
        if infos['category']:
            data['game'] = self.config.get('assignation', {}).get(infos['category'], infos['category']) or channel_info['game']
        self.update_tags(infos['tags'])
        if data:
            self.get_token()
            data = {'channel': data}
            address = '{}/channels/{}'.format(self.apibase, self.config['channel_id'])
            return self.request('put', address, data=data)

    def get_channel_id(self):
        address = '{}/users?login={}'.format(self.apibase, self.config['channel'])
        result = self.request('get', address).json()
        return result['users'][0]['_id']

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