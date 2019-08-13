# coding: utf-8

import time
import json
import ctypes
import logging
import subprocess

import psutil
import requests

logger = logging.getLogger(__name__)

""" 
TODO:
Record all the data in a separate json file
Do a more OOP refactoring, separate services into different files (Twitch/Mixer)
Display an icon in the systray to show if offline or online
"""


GAME_DATA = {
    'r5apex.exe': {
        'game': 'Apex Legends',
    },
    'Overwatch.exe': {
        'game': 'Overwatch',
    },
    'houdinifx.exe': {
        'game': 'Art',
    },
    'sublime_text.exe': {
        'game': 'Science & Technology',
        'tags': ['Software Development']
    },
    'VSCodium.exe': {
        'game': 'Science & Technology',
        'tags': ['Software Development']
    }
}


def getForegroundProcess():
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    h_wnd = user32.GetForegroundWindow()
    pid = ctypes.wintypes.DWORD()
    user32.GetWindowThreadProcessId(h_wnd, ctypes.byref(pid))
    process = psutil.Process(pid.value)
    return process



class ManageStream():

    def __init__(self, channel, client_id, oauth_token):
        self.localisation = 'en-us'
        self.channel = channel
        self.client_id = client_id
        self.client_secret = 'clientsecret'
        self.oauth_token = oauth_token
        self.headers = {
            'Accept': 'application/vnd.twitchtv.v5+json',
            'Client-ID': self.client_id,
            'Authorization': 'OAuth ' + self.oauth_token
         }
        self.channel_id = self.get_channel_id()
        channel = self.get_channel_info()
        self.game = channel['game']
        self.status = channel['status']
        self.redirect = 'http://localhost:777'

    def get_token(self):
        scope = 'user:edit:broadcast channel_editor'
        address = 'https://id.twitch.tv/oauth2/authorize?response_type=code&client_id={}&redirect_uri={}&scope={}&state={}'.format(self.client_id, self.redirect, scope, self.client_secret)

        import socket
        serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        serversocket.bind(('localhost', 777))
        serversocket.listen(5)
        import webbrowser
        webbrowser.open(address)
        while True:
            connection, address = serversocket.accept()
            buf = connection.recv(64)
            if buf:
                break

        print(buf)
        import re
        code = re.search('code=(.*)&', str(buf))
        code = code.group(1)
        print(code)


        address = 'https://id.twitch.tv/oauth2/token?client_id={}&client_secret={}&code={}&grant_type=authorization_code&redirect_uri={}'.format(self.client_id, self.client_secret, code, self.redirect)
        response = requests.post(address)
        print(response.json())
        self.bear_token = response.json()['access_token']
        self.bear_token_refresh = response.json()['refresh_token']

    def refresh_token(self):
        address = 'https://id.twitch.tv/oauth2/token?grant_type=refresh_token&refresh_token={}&client_id={}&client_secret={}'.format(self.bear_token_refresh, self.client_id, self.client_secret)
        response = requests.post(address)
        print(response.json())

    def get_alltags(self):
        cursor = ''
        alltags = {}
        while cursor is not None:
            address = 'https://api.twitch.tv/helix/tags/streams?first=100&after={}'.format(cursor)
            response = requests.get(address, headers=self.headers)
            response = response.json()
            for i in response['data']:
                alltags[i['localization_names'][self.localisation]] = i['tag_id']
            cursor = response['pagination'].get('cursor')
        self.alltags = alltags
        return alltags

    def update_tags(self):
        address = 'https://api.twitch.tv/helix/streams/tags?broadcaster_id={}'.format(self.channel_id)
        headers = {
            'Client-ID': self.client_id,
            'Authorization': 'Bearer ' + self.bear_token
         }
        data = {'tag_ids': [self.alltags['Software Development']]}
        response = requests.put(address, headers=headers, json=data)
        print(response)

    def get_channel_id(self):
        address = 'https://api.twitch.tv/kraken/users?login={}'.format(self.channel)
        response = requests.get(address, headers=self.headers)
        return response.json()['users'][0]['_id']

    def get_channel_info(self):
        address = 'https://api.twitch.tv/kraken/channels/{}'.format(self.channel_id)
        response = requests.get(address, headers=self.headers)
        return response.json()

    def update_channel(self, data):
        address = 'https://api.twitch.tv/kraken/channels/{}'.format(self.channel_id)
        response = requests.put(address, headers=self.headers, json=data)
        logger.info(response)
        logger.debug(response.json())
        return response

    def check_application(self):
        process = getForegroundProcess()
        game = GAME_DATA.get(process.name(), {}).get('game')
        if game and game!=self.game:
            data = {'channel': {'game': game}}
            status = GAME_DATA.get(process.name(), {}).get('status', self.status)
            data['channel']['status'] = status
            response = self.update_channel(data)
            self.game = game

    def main(self):
        with pause_services(["Backblaze Service", "Synergy", "Duplicati", "DbxSvc"]):
            obs = subprocess.Popen('obs64.exe --startstreaming', shell=True, cwd="C:\\Program Files (x86)\\obs-studio\\bin\\64bit\\")
            while obs.poll() is None:
                time.sleep(60)
                self.check_application()




from contextlib import contextmanager

@contextmanager
def pause_services(services):
    for service in services:
        subprocess.Popen('net stop "{}"'.format(service))
    yield
    for service in services:
        subprocess.Popen('net start "{}"'.format(service))



if __name__ == '__main__':
    manager = ManageStream('channelname', 'clientid', 'clientoauth')
    # manager.get_token()
    # manager.refresh_token()
    # manager.get_alltags()
    # manager.update_tags()
    manager.main()


