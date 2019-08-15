# coding: utf-8

import re
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
""" 
TODO:
Do a more OOP refactoring, separate services into different files (Twitch/Mixer)
Display an icon in the systray to show if offline or online
"""


def getForegroundProcess():
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    h_wnd = user32.GetForegroundWindow()
    pid = ctypes.wintypes.DWORD()
    user32.GetWindowThreadProcessId(h_wnd, ctypes.byref(pid))
    process = psutil.Process(pid.value)
    return process



class ManageStream():

    def __init__(self):
        self.load_config()
        self.headers = {
            'Accept': 'application/vnd.twitchtv.v5+json',
            'Client-ID': self.config['Twitch']['client_id'],
            'Authorization': 'OAuth ' + self.config['Twitch']['authorization']['access_token']
         }
        self.channel_id = self.get_channel_id()
        channel = self.get_channel_info()
        self.process = ''
        self.status = channel['status']
        atexit.register(self.save_config)

    def load_config(self):
        with open('streammanager.json') as json_file:
            self.config = json.load(json_file)

    def save_config(self):
        with open('streammanager.json', 'w') as json_file:
            json.dump(self.config, json_file, indent=4)

    def convert_expiration(self):
        now = time.time()
        self.config['Twitch']['authorization']['expires_in'] = now + self.config['Twitch']['authorization']['expires_in'] - 60

    def token_isexpired(self):
        return time.time() > self.config['Twitch']['authorization']['expires_in']

    def get_token(self):
        try:
            if self.token_isexpired():
                self.refresh_token()
            else:
                logger.info('No need to refresh the token')
        except KeyError as e:
            logger.info('Asking for an access code')
            scope = 'user:edit:broadcast channel_editor'
            address = 'https://id.twitch.tv/oauth2/authorize?response_type=code&client_id={}&redirect_uri={}&scope={}&state={}'.format(self.config['Twitch']['client_id'], self.config['Twitch']['redirect_uri'], scope, self.config['Twitch']['client_secret'])

            serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            serversocket.bind(('localhost', 777))
            serversocket.listen(5)
            webbrowser.open(address)
            while True:
                connection, address = serversocket.accept()
                buf = connection.recv(64)
                if buf:
                    break

            code = re.search('code=(.*)&', str(buf))
            code = code.group(1)
            logger.info('The code is {}. Asking for the authorization token'.format(code))

            address = 'https://id.twitch.tv/oauth2/token?client_id={}&client_secret={}&code={}&grant_type=authorization_code&redirect_uri={}'.format(self.config['Twitch']['client_id'], self.config['Twitch']['client_secret'], code, self.config['Twitch']['redirect_uri'])
            response = requests.post(address)
            self.config['Twitch']['authorization'] = response.json()
            self.convert_expiration()

    def refresh_token(self):
        logger.info('Refreshing the token')
        address = 'https://id.twitch.tv/oauth2/token?grant_type=refresh_token&refresh_token={}&client_id={}&client_secret={}'.format(self.config['Twitch']['authorization']['refresh_token'], self.config['Twitch']['client_id'], self.config['Twitch']['client_secret'])
        response = requests.post(address)
        self.config['Twitch']['authorization'] = response.json()
        self.convert_expiration()
        return response

    def get_alltags(self):
        cursor = ''
        alltags = {}
        while cursor is not None:
            address = 'https://api.twitch.tv/helix/tags/streams?first=100&after={}'.format(cursor)
            response = requests.get(address, headers=self.headers)
            response = response.json()
            for i in response['data']:
                alltags[i['localization_names'][self.config['Twitch']['localisation']]] = i['tag_id']
            cursor = response['pagination'].get('cursor')
        self.alltags = alltags
        return alltags

    def get_tagsid(self, tags):
        tagsid = [v for k,v in self.alltags.items() if k in tags]
        return tagsid

    def update_tags(self, tags):
        self.get_token()
        if self.config['Twitch'].get('forced_tags'):
            tags = self.config['Twitch']['forced_tags'] + tags

        logger.info('Set tags to: {}'.format(tags))
        self.get_alltags()
        tagsid = self.get_tagsid(tags)
        address = 'https://api.twitch.tv/helix/streams/tags?broadcaster_id={}'.format(self.channel_id)
        headers = {
            'Client-ID': self.config['Twitch']['client_id'],
            'Authorization': 'Bearer ' + self.config['Twitch']['authorization']['access_token']
         }
        data = {'tag_ids': tagsid}
        response = requests.put(address, headers=headers, json=data)
        if not response:
            logger.error(response.json())
        return response

    def get_channel_id(self):
        address = 'https://api.twitch.tv/kraken/users?login={}'.format(self.config['Twitch']['channel'])
        response = requests.get(address, headers=self.headers)
        return response.json()['users'][0]['_id']

    def get_channel_info(self):
        address = 'https://api.twitch.tv/kraken/channels/{}'.format(self.channel_id)
        response = requests.get(address, headers=self.headers)
        return response.json()

    def update_channel(self, data):
        if self.config['Twitch'].get('forced_status'):
            data['status'] =  self.config['Twitch']['forced_status']

        address = 'https://api.twitch.tv/kraken/channels/{}'.format(self.channel_id)
        response = requests.put(address, headers=self.headers, json=data)
        if not response:
            logger.error(response.json())
        return response

    def check_application(self):
        process = getForegroundProcess()
        category = self.config['appdata'].get(process.name(), {}).get('category')
        if category and process!=self.process:
            data = {'channel': {'category': category}}
            status = self.config['appdata'].get(process.name(), {}).get('status', self.status)
            data['channel']['status'] = status
            response = self.update_channel(data)
            tags = self.config['appdata'].get(process.name(), {}).get('tags')
            response = self.update_tags(tags)
            self.process = process

    def main(self):
        with pause_services(self.config['services']):
            obs = subprocess.Popen('obs64.exe', shell=True, cwd="C:\\Program Files (x86)\\obs-studio\\bin\\64bit\\")
            while obs.poll() is None:
                time.sleep(60)
                self.check_application()


@contextmanager
def pause_services(services):
    for service in services:
        subprocess.Popen('net stop "{}"'.format(service))
    yield
    for service in services:
        subprocess.Popen('net start "{}"'.format(service))



if __name__ == '__main__':
    manager = ManageStream()
    manager.main()


