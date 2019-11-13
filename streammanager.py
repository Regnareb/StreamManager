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
        self.services = []
        for service in self.config['streamservices']:
            # Call the class dynamically
            self.services.append(getattr(sys.modules[__name__], service)(self.config['streamservices'][service]))

    def create_clip(self):
        for service in self.services:
            service.create_clip()

    def update_channel(self, title, description, category, tags):
        for service in self.services:
            service.update_channel(title, description, category, tags)

    def check_application(self):
        self.load_config()
        process = getForegroundProcess()
        tags = self.config['appdata'].get(process.name(), {}).get('tags')
        title = self.config['appdata'].get(process.name(), {}).get('title', self.config['base'].get('title'))
        category = self.config['appdata'].get(process.name(), {}).get('category')
        description = self.config['appdata'].get(process.name(), {}).get('description', self.config['base'].get('description'))
        if category and process!=self.process:
            if self.config['base'].get('forced_tags'):
                tags = self.config['base']['forced_tags'] + tags
            if self.config['base'].get('forced_title'):
                title = self.config['base']['forced_title']
            if self.config['base'].get('forced_description'):
                description = self.config['base']['forced_description']
            logger.debug('title: "{}" | description: "{}" | category: "{}" | tags: "{}" | '.format(title, description, category, tags))
            self.update_channel(title, description, category, tags)
            self.process = process

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
            authorization_url, state = self.oauth2.authorization_url(self.config['authorization_base_url'], state=self.config['client_secret'])
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
        # oauthlib.oauth2.rfc6749.errors.InvalidGrantError: (invalid_grant) Refresh token is invalid, has been revoked, or has already been used.
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

    def update_channel(self, title, description, category, tags):
        data = {}
        channel_info = self.get_channel_info()
        data['status'] = title or channel_info['status']
        data['game'] = self.config.get('assignation', {}).get(category, category) or channel_info['game']
        if data:
            data = {'channel': data}
            address = '{}/channels/{}'.format(self.apibase, self.config['channel_id'])
            return super().update_channel('put', address, data)

    def get_channel_id(self):
        address = '{}/users?login={}'.format(self.apibase, self.config['channel'])
        result = super().get_channel_id(address)
        return result['users'][0]['_id']

    def get_alltags(self):
        cursor = ''
        alltags = {}
        while cursor is not None:
            address = '{}tags/streams?first=100&after={}'.format(self.apibase2, cursor)
            response = requests.get(address, headers=self.headers)
            response = response.json()
            for i in response['data']:
                alltags[i['localization_names'][self.config['localisation']]] = i['tag_id']
            cursor = response['pagination'].get('cursor')
        self.alltags = alltags
        return alltags

    def get_tagsid(self, tags):
        tagsid = [v for k,v in self.alltags.items() if k in tags]
        return tagsid

    def update_tags(self, tags):
        self.get_token()
        logger.info('Set tags to: {}'.format(tags))
        self.get_alltags()
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

    def update_channel(self, title, description, category, tags):
        data = {}
        if title:
            data['name'] = title
        # if description:  # Not supported anymore
        #     data['description'] = description
        if category:
            category = self.config.get('assignation', {}).get(category, category)
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



if __name__ == '__main__':
    manager = ManageStream()
    # manager.create_services()
    manager.main()
