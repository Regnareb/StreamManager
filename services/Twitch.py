# coding: utf-8
import time
import logging
import asyncio
import threading
import functools
import common.tools as tools
from common.service import *
logger = logging.getLogger(__name__)
import twitchio
from twitchio.ext import commands

@tools.decorate_all_methods(tools.catch_exception(logger=logger))
class Main(Service):
    name = 'Twitch'
    scope = "user:edit:broadcast channel_editor clips:edit chat:read chat:edit"
    authorization_base_url = "https://id.twitch.tv/oauth2/authorize"
    token_url = "https://id.twitch.tv/oauth2/token"
    redirect_uri = "http://localhost:60779/"
    apibase = 'https://api.twitch.tv/kraken'
    apibase2 = 'https://api.twitch.tv/helix'
    devurl = 'https://dev.twitch.tv/console/apps'
    features = {'title': True, 'category': True, 'tags': True, 'clips': True, 'markers': True}

    def set_headers(self):
        super().set_headers()
        self.headers['Accept'] = 'application/vnd.twitchtv.v5+json'

    def get_channel_info(self):
        self.get_token()
        address = '{}/channels?broadcaster_id={}'.format(self.apibase2, self.config['channel_id'])
        result = self.request('get', address, headers=self.headers2).json()['data'][0]
        address = '{}/streams?user_id={}'.format(self.apibase2, self.config['channel_id'])
        online = self.request('get', address, headers=self.headers2).json()
        try:
            online = online['data']
        except KeyError:
            print(online)
        try:
            viewers = online[0]['viewer_count']
            online = True
        except (IndexError, KeyError):
            viewers = None
            online = False
        self.infos = {'online': online, 'title': result['title'], 'name': result['broadcaster_name'], 'category': result['game_name'], 'viewers': viewers}
        return self.infos

    def get_gamedescription(self):
        general_description = self.manager.config['base']['description'] or ''
        if self.manager.config['base']['forced_description']:
            return general_description
        infos = self.get_channel_info()
        imlucky = self.manager.config.get('appdata', {}).get(infos['category'], {})
        if imlucky and imlucky.get('Twitch', {}).get('name', '') == infos['category']:
            return imlucky.get('description') or general_description
        for i in self.manager.config.get('appdata', {}).values():
            if infos['category'] == i.get('Twitch', {}).get('name', ''):
                return i.get('description') or general_description
        return general_description

    @functools.lru_cache(maxsize=128)
    def query_category(self, category):
        result = {}
        if category:
            params = {'query': category}
            address = '{}/search/categories'.format(self.apibase2)
            response = self.request('get', address, headers=self.headers2, params=params)
            for i in response.json()['data'] or []:
                result[i['name']] = str(i['id'])
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
            data['title'] = infos['title']
        if infos.get('category'):
            data['game_id'] = self.query_category(infos['category'])[infos['category']]
        if infos.get('tags'):
            self.update_tags(infos['tags'])
        if data:
            self.get_token()
            address = '{}/channels?broadcaster_id={}'.format(self.apibase2, self.config['channel_id'])
            return self.request('patch', address, headers=self.headers2, data=data)

    def get_channel_id(self):
        address = '{}/users'.format(self.apibase2)
        result = self.request('get', address, self.headers2).json()
        self.config['channel_id'] = result['data'][0]['id']
        self.config['name'] = result['data'][0]['display_name']

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


    def create_commandbot(self):
        # Clean up the old bot if there is any
        loop = asyncio.get_event_loop()
        tasks = asyncio.all_tasks(loop)
        [i.cancel() for i in tasks]
        loop.stop()

        asyncio.set_event_loop(asyncio.new_event_loop())  # Restart a new loop
        loop = asyncio.get_event_loop()
        def exception_handler(loop, context):
            if "exception" not in context:
                loop.default_exception_handler(context)
            else:
                self.manager.commandbots['Twitch'] = None
                print('Bypass timeout exception and restart commandbot')

        loop.set_exception_handler(exception_handler)
        self.thread = threading.Thread(daemon=True, target=loop.run_forever)
        self.thread.start()

        self.manager.commandbots['Twitch'] = Bot(self.config['name'])
        self.future = asyncio.run_coroutine_threadsafe(self.manager.commandbots['Twitch'].start(), loop)


class Bot(commands.Bot):
    def __init__(self, name):
        self.manager = common.manager.ManageStream()
        client_id = self.manager.config['streamservices']['Twitch']['client_id']
        irc_token = 'oauth:' + self.manager.config['streamservices']['Twitch']['authorization']['access_token']
        super().__init__(irc_token=irc_token, client_id=client_id, nick=name, prefix='!', initial_channels =['#' + name])

    async def event_ready(self):
        logger.info(f'Command bot for Twitch connected to chat')

    async def event_message(self, message):
        if message.content in ['!game']:
            description = self.manager.services['Twitch'].get_gamedescription()
            if description:
                ctx = twitchio.Context(message=message, channel=message.channel, user=message.author, prefix='!')
                await ctx.send(description)
