# coding: utf-8

import os
import re
import sys
import time
import json
import urllib
import atexit
import socket
import ctypes
import inspect
import logging
import functools
import threading
import webbrowser
import subprocess
from contextlib import contextmanager

import psutil
import requests
import keyboard
from requests_oauthlib import OAuth2Session
from oauthlib.oauth2.rfc6749.errors import InvalidGrantError, MissingTokenError, InvalidClientError, InvalidTokenError, InvalidClientIdError

logger = logging.getLogger(__name__)
logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

def getForegroundProcess():
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    h_wnd = user32.GetForegroundWindow()
    pid = ctypes.wintypes.DWORD()
    user32.GetWindowThreadProcessId(h_wnd, ctypes.byref(pid))
    process = psutil.Process(pid.value)
    return process

def threaded(func):
    @functools.wraps(func)
    def async_func(*args, **kwargs):
        func_hl = threading.Thread(target=func, args=args, kwargs=kwargs)
        func_hl.start()
        return func_hl
    return async_func

@contextmanager
def pause_services(services):
    # Use pssuspend and kill -STOP on mac
    for service in services:
        subprocess.Popen('net stop "{}"'.format(service))
    yield
    for service in services:
        subprocess.Popen('net start "{}"'.format(service))


class ManageStream():
    def __init__(self):
        self.process = ''
        self.services = {}
        self.currentkey = set()
        self.config_filepath = os.path.join(os.path.dirname(__file__), 'streammanager.json')
        self.load_config()
        self.create_services()
        self.shortcuts()
        atexit.register(self.save_config)

    def load_config(self):
        with open(self.config_filepath) as json_file:
            self.config = json.load(json_file)

    def save_config(self):
        for service in self.services:
            self.config['streamservices'][service.name] = service.config
        with open(self.config_filepath, 'w') as json_file:
            json.dump(self.config, json_file, indent=4)

    def shortcuts(self):
        keyboard.add_hotkey('ctrl+F9', self.create_clip)

    def create_services(self):
        for service in self.config['streamservices']:
            self.create_service(service)

    def create_service(self, service):
        if self.config['streamservices'][service]['enabled'] and service not in self.services:
            self.services[service] = getattr(sys.modules[__name__], service)(self.config['streamservices'][service])  # Call the class dynamically

    def create_clip(self):
        for service in self.services:
            if service.config['enabled']:
                service.create_clip()

    def update_channel(self, infos):
        for service in self.services:
            if service.config['enabled']:
                service.update_channel(infos)

    def check_application(self):
        self.load_config()
        process = getForegroundProcess()
        category = self.config['appdata'].get(process.name(), {}).get('category')
        if category and process!=self.process:
            infos = self.get_informations(process.name())
            infos['category'] = category
            logger.debug(f'title: "{infos['title']}" | description: "{infos['description']}" | category: "{infos['category']}" | tags: "{infos['tags']}"')
            self.update_channel(infos)
            self.process = process

    def get_informations(self, name):
        infos = {}
        infos['tags'] = self.config['base'].get('forced_tags', []) + self.config['appdata'].get(name, {}).get('tags', [])
        infos['title'] = self.config['base'].get('forced_title') or self.config['appdata'].get(name, {}).get('title') or self.config['base'].get('title', '')
        infos['description'] = self.config['base'].get('forced_description') or self.config['appdata'].get(name, {}).get('description') or self.config['base'].get('description', '')
        return infos

    def main(self):
        with pause_services(self.config['base']['services']):
            obs = subprocess.Popen('obs64.exe --startreplaybuffer', shell=True, cwd="C:\\Program Files (x86)\\obs-studio\\bin\\64bit\\")
            while obs.poll() is None:
                time.sleep(4)
                self.check_application()


class Service():
    def __init__(self, config):
        self.config = config
        self.oauth2 = OAuth2Session(token=self.config['authorization'], client_id=self.config['client_id'], scope=self.config['scope'], redirect_uri=self.config['redirect_uri'])
        self.get_token()
        if not self.config.get('channel_id'):
            self.config['channel_id'] = self.get_channel_id()

    def set_headers(self):
        self.headers = {
            'Client-ID': self.config['client_id'],
            'Authorization': 'OAuth ' + self.config['authorization']['access_token']
         }
        self.headers2 = {
            'Client-ID': self.config['client_id'],
            'Authorization': 'Bearer ' + self.config['authorization']['access_token']
         }

    def token_isexpired(self):
        return time.time() > self.config['authorization']['expires_at']

    def get_token(self):
        try:
            if self.token_isexpired():
                self.refresh_token()
        except (KeyError, Warning, InvalidGrantError):
            logger.info('Asking for an access code for {}'.format(self.name))
            port = re.search(r':(\d*)$', self.config['redirect_uri'])
            port = int(port.group(1))
            authorization_url, state = self.oauth2.authorization_url(self.config['authorization_base_url'], state=self.config['client_secret'], access_type='offline')
            serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            serversocket.bind(('localhost', port))
            serversocket.listen(5)
            webbrowser.open(authorization_url)
            while True:
                connection, address = serversocket.accept()
                buf = connection.recv(4096)
                if buf:
                    break
            code = re.search('code=(.*?)&', str(buf))
            code = code.group(1)
            code = urllib.parse.unquote(code)
            logger.debug('The code is {}. Asking for the authorization token'.format(code))
            self.config['authorization'] = self.oauth2.fetch_token(self.config['token_url'], code, include_client_id=True, client_secret=self.config['client_secret'])
        finally:
            self.set_headers()

    def refresh_token(self):
        try:
            self.config['authorization'] = self.oauth2.refresh_token(self.config['token_url'], **{'client_id': self.config['client_id'], 'client_secret': self.config['client_secret']})
        except InvalidGrantError:
            logger.error("Couldn't refresh the token")
            raise

    def request(self, action, address, headers=None, data=None):
        if not headers:
            headers = self.headers
        action = getattr(requests, action)
        response = action(address, headers=headers, json=data)
        curframe = inspect.currentframe()
        outframe = inspect.getouterframes(curframe, 2)[1][3]
        self.log_requests(outframe, address, response)
        return response

    def log_requests(self, action, address, response):
        if not response:
            logger.error('{} - {}: {} {}'.format(self.name, action, address, response.json()))
        else:
            logger.debug(response.json())

    def get_channel_info(self, address):
        response = self.request('get', address)
        return response.json()

    def update_channel(self, action, address, data):
        self.get_token()
        response = self.request(action, address, data=data)
        return response

    def get_channel_id(self, address):
        response = self.request('get', address)
        return response.json()

    def create_clip(self, address):
        response = self.request('post', address, headers=self.headers)
        return response




class Twitch(Service):
    def __init__(self, config):
        self.name = 'Twitch'
        self.apibase = 'https://api.twitch.tv/kraken'
        self.apibase2 = 'https://api.twitch.tv/helix'
        super().__init__(config)

    def set_headers(self):
        super().set_headers()
        self.headers['Accept'] = 'application/vnd.twitchtv.v5+json'

    def get_channel_info(self):
        address = '{}/channels/{}'.format(self.apibase, self.config['channel_id'])
        return super().get_channel_info(address)

    def update_channel(self, infos):
        data = {}
        channel_info = self.get_channel_info()
        data['status'] = infos['title'] or channel_info['status']
        data['game'] = self.config.get('assignation', {}).get(infos['category'], infos['category']) or channel_info['game']
        self.update_tags(infos['tags'])
        if data:
            data = {'channel': data}
            address = '{}/channels/{}'.format(self.apibase, self.config['channel_id'])
            return super().update_channel('put', address, data)

    def get_channel_id(self):
        address = '{}/users?login={}'.format(self.apibase, self.config['channel'])
        result = super().get_channel_id(address)
        return result['users'][0]['_id']

    @property
    def alltags(self):
        try:
            return self._alltags
        except AttributeError:
            self._alltags = {}
            cursor = ''
            while cursor is not None:
                address = '{}tags/streams?first=100&after={}'.format(self.apibase2, cursor)
                response = requests.get(address, headers=self.headers)
                response = response.json()
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
            address = '{}streams/tags?broadcaster_id={}'.format(self.apibase2, self.config['channel_id'])
            data = {'tag_ids': tagsid}
            response = requests.put(address, headers=self.headers2, json=data)
            if not response:
                logger.error(response.json())
            return response

    @threaded
    def create_clip(self):
        self.get_token()
        address = '{}streams?user_id={}'.format(self.apibase2, self.config['channel_id'])
        response = self.request('get', address)
        online = response.json()['data']
        if online:
            address = '{}clips?broadcaster_id={}'.format(self.apibase2, self.config['channel_id'])
            response = self.request('post', address, headers=self.headers2)
            for i in range(15):  # Check if the clip has been created
                address = '{}clips?id={}'.format(self.apibase2, response.json()['data'][0]['id'])
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




class Mixer(Service):
    def __init__(self, config):
        self.name = 'Mixer'
        self.apibase = 'https://mixer.com/api/v1'
        super().__init__(config)

    def get_channel_info(self):
        address = '/{}channels/{}'.format(self.apibase, self.config['channel_id'])
        return super().get_channel_info(address)

    def update_channel(self, infos):
        data = {}
        if title:
            data['name'] = infos['title']
        if category:
            category = self.config.get('assignation', {}).get(infos['category'], infos['category'])
            data['typeId'] = self.get_game_id(category)
        if data:
            address = '{}/channels/{}'.format(self.apibase, self.config['channel_id'])
            return super().update_channel('patch', address, data)

    def get_channel_id(self):
        address = '{}/channels/{}'.format(self.apibase, self.config['channel'])
        return super().get_channel_id(address)['id']

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



class Youtube(Service):
    def __init__(self, config):
        self.name = 'Youtube'
        self.apibase = 'https://www.googleapis.com/youtube/v3'
        config['channel_id'] = ''  # Reset the id each time because Youtube
        super().__init__(config)

    def get_channel_info(self):
        address = '{}/liveBroadcasts?part=snippet&broadcastType=persistent&mine=true'.format(self.apibase)
        return super().get_channel_info(address)

    def update_channel(self, infos):
        data = {'id': self.config['channel_id'], 'snippet': {}}
        if title:
            data['snippet']['title'] = infos['title']
        if description:
            data['snippet']['description'] = infos['description']
        if category:
            category = self.config.get('assignation', {}).get(infos['category'], infos['category'])
            data['snippet']['categoryId'] = self.gamesid.get(category, '')
        if data['snippet']:
            address = '{}/videos?part=snippet'.format(self.apibase)
            return super().update_channel('put', address, data)

    def get_channel_id(self):
        result = self.get_channel_info()
        self.config['channel_id'] = result['items'][0]['id']
        return result['items'][0]['id']

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

if __name__ == '__main__':
    manager = ManageStream()
    # manager.create_services()
    manager.main()
