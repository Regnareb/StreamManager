# coding: utf-8

import os
import re
import sys
import time
import json
import atexit
import socket
import ctypes
import inspect
import logging
import webbrowser
import subprocess
from contextlib import contextmanager

import psutil
import requests
from requests_oauthlib import OAuth2Session

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


@contextmanager
def pause_services(services):
    for service in services:
        subprocess.Popen('net stop "{}"'.format(service))
    yield
    for service in services:
        subprocess.Popen('net start "{}"'.format(service))


class ManageStream():

    def __init__(self):
        self.title = ''
        self.description = ''
        self.process = ''
        self.config_filepath = os.path.join(os.path.dirname(__file__), 'streammanager.json')
        self.load_config()
        self.create_services()
        atexit.register(self.save_config)

    def load_config(self):
        with open(self.config_filepath) as json_file:
            self.config = json.load(json_file)

    def save_config(self):
        for service in self.services:
            self.config['streamservices'][service.name] = service.config
        with open(self.config_filepath, 'w') as json_file:
            json.dump(self.config, json_file, indent=4)

    def create_services(self):
        self.services = []
        for service in self.config['streamservices']:
            # Call the class dynamically
            self.services.append(getattr(sys.modules[__name__], service)(self.config['streamservices'][service]))

    def update_channel(self, title, description, category, tags):
        for service in self.services:
            service.update_channel(title, description, category, tags)

    def check_application(self):
        process = getForegroundProcess()
        tags = self.config['appdata'].get(process.name(), {}).get('tags')
        title = self.config['appdata'].get(process.name(), {}).get('title', self.title)
        category = self.config['appdata'].get(process.name(), {}).get('category')
        description = self.config['appdata'].get(process.name(), {}).get('description', self.description)
        if category and process!=self.process:
            if self.config.get('forced_tags'):
                tags = self.config['forced_tags'] + tags
            if self.config.get('forced_title'):
                title = self.config['forced_title']
            if self.config.get('forced_description'):
                description = self.config['forced_description']
            self.update_channel(title, description, category, tags)
            self.process = process

    def main(self):
        with pause_services(self.config['services']):
            obs = subprocess.Popen('obs64.exe', shell=True, cwd="C:\\Program Files (x86)\\obs-studio\\bin\\64bit\\")
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

    def token_isexpired(self):
        return time.time() > self.config['authorization']['expires_at']

    def get_token(self):
        try:
            if self.token_isexpired():
                self.refresh_token()
        except KeyError:
            logger.info('Asking for an access code')
            port = re.search(':(\d*)$', self.config['redirect_uri'])
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
            logger.debug('The code is {}. Asking for the authorization token'.format(code))

            self.config['authorization'] = self.oauth2.fetch_token(self.config['token_url'], code, include_client_id=True, client_secret=self.config['client_secret'])
        finally:
            self.set_headers()

    def refresh_token(self):
        self.config['authorization'] = self.oauth2.refresh_token(self.config['token_url'], **{'client_id': self.config['client_id'], 'client_secret': self.config['client_secret']})

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
            logger.error('{}: {} {}'.format(action, address, response.json()))
        else:
            logger.debug(response.json())

    def get_channel_info(self, address):
        response = self.request('get', address)
        return response.json()

    def update_channel(self, action, address, data):
        self.get_token()
        response = self.request(action, address, data=data)
        return response

    def update_tags(self, tags):
        self.get_token()
        response = self.request(action, address, data=data)
        return response

    def get_channel_id(self, address):
        response = self.request('get', address)
        return response.json()





class Twitch(Service):
    def __init__(self, config):
        super().__init__(config)
        self.name = 'Twitch'

    def set_headers(self):
        super().set_headers()
        self.headers['Accept'] = 'application/vnd.twitchtv.v5+json'

    def get_channel_info(self):
        address = 'https://api.twitch.tv/kraken/channels/{}'.format(self.config['channel_id'])
        return super().get_channel_info(address)

    def update_channel(self, title, description, category, tags):
        data = {}
        if title:
            data['status'] = title
        if category:
            data['game'] = self.config.get('assignation', {}).get(category, category)
        if data:
            data = {'channel': data}
            address = 'https://api.twitch.tv/kraken/channels/{}'.format(self.config['channel_id'])
            return super().update_channel('put', address, data)

    def get_channel_id(self):
        address = 'https://api.twitch.tv/kraken/users?login={}'.format(self.config['channel'])
        result = super().get_channel_id(address)
        return result['users'][0]['_id']

    def get_alltags(self):
        cursor = ''
        alltags = {}
        while cursor is not None:
            address = 'https://api.twitch.tv/helix/tags/streams?first=100&after={}'.format(cursor)
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
        address = 'https://api.twitch.tv/helix/streams/tags?broadcaster_id={}'.format(self.config['channel_id'])
        headers = {
            'Client-ID': self.config['client_id'],
            'Authorization': 'Bearer ' + self.config['authorization']['access_token']
         }
        data = {'tag_ids': tagsid}
        response = requests.put(address, headers=headers, json=data)
        if not response:
            logger.error(response.json())
        return response



if __name__ == '__main__':
    manager = ManageStream()
    # manager.create_services()
    manager.main()

