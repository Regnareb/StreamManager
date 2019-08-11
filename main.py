# -*- coding: utf-8 -*-

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

channel_id = 0  # The channel ID you want to manage
client_id = 'x'  # The Client-Id you get when creating the application on dev.twitch.tv/
oauth_token = 'x'  # The secret token you create on your application settings
status = 'Title of the stream'

game_data = {
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


def update_channel(data):
        address = 'https://api.twitch.tv/kraken/channels/{}'.format(channel_id)
        headers = {
            'Accept': 'application/vnd.twitchtv.v5+json',
            'Client-ID': client_id,
            'Authorization': 'OAuth ' + oauth_token
         }
        response = requests.put(address, headers=headers, json=data)
        return response


def check(currentgame):
    process = getForegroundProcess()
    game = game_data.get(process.name(), {}).get('game')
    if game and game!=currentgame:
        data = {'channel': {'game': game}}
        gamestatus = game_data.get(process.name(), {}).get('status')
        if gamestatus:
            data['channel']['status'] = gamestatus
        response = update_channel(data)
        logger.info(response)
        return game
    else:
        return currentgame


def main():
    subprocess.Popen('net stop "Backblaze Service"')
    subprocess.Popen('net stop "Synergy"')
    subprocess.Popen('net stop "Duplicati"')
    subprocess.Popen('net stop "DbxSvc"')
    obs = subprocess.Popen('obs64.exe --startstreaming', shell=True, cwd="C:\\Program Files (x86)\\obs-studio\\bin\\64bit\\")
    game = ''
    while obs.poll() is None:
        time.sleep(60)
        game = check(game)
    subprocess.Popen('net start "Backblaze Service"')
    subprocess.Popen('net start "Synergy"')
    subprocess.Popen('net start "Duplicati"')
    subprocess.Popen('net start "DbxSvc"')


if __name__ == '__main__':
    main()
