# coding: utf-8

import os
import re
import sys
import time
import json
import atexit
import socket
import ctypes
import logging
import webbrowser
import subprocess
from contextlib import contextmanager

import psutil
import requests

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
        self.status = ''
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
            self.services.append(getattr(sys.modules[__name__], service)(self.config['streamservices'][service]))

    def update_channel(self, data):
        for service in self.services:
            service.update_channel(data)

    def update_tags(self, data):
        for service in self.services:
            service.update_tags(data)

    def check_application(self):
        process = getForegroundProcess()
        category = self.config['appdata'].get(process.name(), {}).get('category')
        if category and process!=self.process:
            data = {'channel': {'game': category}}
            if self.config.get('forced_status'):
                data['channel']['status'] = self.config['forced_status']
            else:
                data['channel']['status'] = self.config['appdata'].get(process.name(), {}).get('status', self.status)
            self.update_channel(data)
            tags = self.config['appdata'].get(process.name(), {}).get('tags')
            self.update_tags(tags)
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
        self.get_token()
        self.headers = {
            'Client-ID': self.config['client_id'],
            'Authorization': 'OAuth ' + self.config['authorization']['access_token']
         }

    def convert_expiration(self):
        self.config['authorization']['expires_in'] = now = time.time() + self.config['authorization']['expires_in'] - 60

    def token_isexpired(self):
        return time.time() > self.config['authorization']['expires_in']

    def get_token(self, address_code, address_token):
        try:
            if self.token_isexpired():
                self.refresh_token()
            else:
                logger.info('No need to refresh the token')
        except KeyError as e:
            logger.info('Asking for an access code')
            serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            serversocket.bind(('localhost', 777))
            serversocket.listen(5)
            webbrowser.open(address_code)
            while True:
                connection, address = serversocket.accept()
                buf = connection.recv(64)
                if buf:
                    break

            code = re.search('code=(.*)&', str(buf))
            code = code.group(1)
            logger.info('The code is {}. Asking for the authorization token'.format(code))
            address_token = address_token.format(code)
            response = requests.post(address_token)
            self.log_requests('request_token', address_token, response)
            self.config['authorization'] = response.json()
            self.convert_expiration()

    def refresh_token(self, address):
        logger.info('Refreshing the token')
        response = requests.post(address)
        self.log_requests('refresh_token', address, response)
        self.authorization = response.json()
        return response

    def get_channel_info(self, address):
        response = requests.get(address, headers=self.headers)
        self.log_requests('get_channel_info', address, response)
        return response.json()

    def update_channel(self, address, data):
        self.get_token()
        response = requests.put(address, headers=self.headers, json=data)
        self.log_requests('update_channel', address, response)
        return response

    def log_requests(self, action, address, response):
        if not response:
            logger.error('{}: {} {}'.format(action, address, response.json()))



class Twitch(Service):
    def __init__(self, config):
        super().__init__(config)
        self.name = 'Twitch'
        self.headers = {
            'Accept': 'application/vnd.twitchtv.v5+json',  # Twitch only
            'Client-ID': self.config['client_id'],
            'Authorization': 'OAuth ' + self.config['authorization']['access_token']
         }
        if not self.config.get('channel_id'):
            self.config['channel_id'] = self.get_channel_id()

    def get_channel_info(self):
        address = 'https://api.twitch.tv/kraken/channels/{}'.format(self.config['channel_id'])
        return super().get_channel_info(address)

    def update_channel(self, data):
        address = 'https://api.twitch.tv/kraken/channels/{}'.format(self.config['channel_id'])
        return super().update_channel(address, data)

    def refresh_token(self):
        address = 'https://id.twitch.tv/oauth2/token?grant_type=refresh_token&refresh_token={}&client_id={}&client_secret={}'.format(self.config['refresh_token'], self.config['client_id'], self.config['client_secret'])  # ajouter ['authorization']
        return super().refresh_token(address)

    def get_token(self):
        address = 'https://id.twitch.tv/oauth2/authorize?response_type=code&client_id={}&redirect_uri={}&scope={}&state={}'.format(self.config['client_id'], self.config['redirect_uri'], self.config['scope'], self.config['client_secret'])
        address_token = 'https://id.twitch.tv/oauth2/token?client_id={}&client_secret={}&code={{}}&grant_type=authorization_code&redirect_uri={}'.format(self.config['client_id'], self.config['client_secret'], self.config['redirect_uri'])
        return super().get_token(address, address_token)

    def get_channel_id(self):
        address = 'https://api.twitch.tv/kraken/users?login={}'.format(self.config['channel'])
        response = requests.get(address, headers=self.headers)
        self.log_requests('get_channel_id', address, response)
        return response.json()['users'][0]['_id']

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

