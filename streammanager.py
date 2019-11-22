# coding: utf-8
import os
import time
import json
import atexit
import logging
import subprocess

import keyboard
import tools

logger = logging.getLogger(__name__)
logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

SERVICES = tools.loadmodules('services')


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
        for name, service in self.services.items():
            self.config['streamservices'][name] = service.config
        with open(self.config_filepath, 'w') as json_file:
            json.dump(self.config, json_file, indent=4)

    def shortcuts(self):
        keyboard.add_hotkey('ctrl+F9', self.create_clip)

    def create_services(self):
        for service in SERVICES.values():
            self.create_service(service)

    def create_service(self, service):
        if self.config['streamservices'].get(service.Main.name, {}).get('enabled', True) and service.Main.name not in self.services:
            self.services[service.Main.name] = service.Main(self.config['streamservices'].get(service.Main.name))

    def create_clip(self):
        for service in self.services.values():
            if service.config['enabled']:
                service.create_clip()

    def update_channel(self, infos):
        for service in self.services.values():
            if service.config['enabled']:
                service.update_channel(infos)

    def check_application(self):
        self.load_config()
        process = tools.getForegroundProcess()
        category = self.config['appdata'].get(process.name(), {}).get('category')
        if category and process!=self.process:
            infos = self.get_informations(process.name())
            infos['category'] = category
            logger.debug(f"title: {infos['title']} | description: {infos['description']} | category: {infos['category']} | tags: {infos['tags']}")
            self.update_channel(infos)
            self.process = process

    def get_informations(self, name):
        infos = {}
        infos['tags'] = self.config['base'].get('forced_tags', []) + self.config['appdata'].get(name, {}).get('tags', [])
        infos['title'] = self.config['base'].get('forced_title') or self.config['appdata'].get(name, {}).get('title') or self.config['base'].get('title', '')
        infos['description'] = self.config['base'].get('forced_description') or self.config['appdata'].get(name, {}).get('description') or self.config['base'].get('description', '')
        return infos

    def main(self):
        with tools.pause_services(self.config['base']['services']):
            obs = subprocess.Popen('obs64.exe --startreplaybuffer', shell=True, cwd="C:\\Program Files (x86)\\obs-studio\\bin\\64bit\\")
            while obs.poll() is None:
                time.sleep(4)
                self.check_application()


if __name__ == '__main__':
    manager = ManageStream()
    # manager.create_services()
    manager.main()
