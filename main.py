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
Implement tags when the API is ready
Display an icon in the systray to show if offline or online
"""

# https://api.twitch.tv/kraken/oauth2/authorize?response_type=token&client_id=CLIENT_ID&redirect_uri=REDIRECT_URL&scope=channel_editor



GAME_DATA = {
    'r5apex.exe': {
        'game': 'Apex Legends',
    },
    'Overwatch.exe': {
        'game': 'Overwatch',
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
        self.channel = channel
        self.client_id = client_id
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
        subprocess.Popen('net stop "Backblaze Service"')
        subprocess.Popen('net stop "Synergy"')
        subprocess.Popen('net stop "Duplicati"')
        subprocess.Popen('net stop "DbxSvc"')
        obs = subprocess.Popen('obs64.exe --startstreaming', shell=True, cwd="C:\\Program Files (x86)\\obs-studio\\bin\\64bit\\")
        while obs.poll() is None:
            time.sleep(60)
            self.check_application()
        subprocess.Popen('net start "Backblaze Service"')
        subprocess.Popen('net start "Synergy"')
        subprocess.Popen('net start "Duplicati"')
        subprocess.Popen('net start "DbxSvc"')


if __name__ == '__main__':
    manager = ManageStream('username', 'x', 'x')
    manager.main()

