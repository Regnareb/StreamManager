# coding: utf-8
import os
import time
import json
import atexit
import logging
import subprocess
import concurrent.futures

import keyboard

import common.tools as tools

logger = logging.getLogger(__name__)
logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

SERVICES = tools.loadmodules(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')), 'services')


class ManageStream(tools.Borg):
    def __init__(self):
        super().__init__()
        if not self._Borg__shared_state:
            self.process = ''
            self.config = {}
            self.services = {}
            self.currentkey = set()
            self.config_filepath = os.path.join(os.path.dirname(__file__), '..', 'data', 'settings.json')
            self.load_config()
            self.shortcuts()
            atexit.register(self.save_config)

    def conform_preferences(self):
        template = {
        "streamservices": {service.Main.name: service.Main.default_config() for service in SERVICES.values()},
        "appdata": {},
        "base": {
            "title": "",
            "description": "",
            "services": [],
            "processes": [],
            "category": "",
            "tags": [],
            "forced_category": False,
            "forced_title": False,
            "forced_description": False,
            "forced_tags": False
            },
        "assignations": {}
        }
        for key, value in template.items():
            self.config.setdefault(key, value)
            for k, v in value.items():
                self.config[key].setdefault(k, v)

    def load_config(self):
        try:
            with open(self.config_filepath) as json_file:
                self.config = json.load(json_file)
        except FileNotFoundError:
            pass
        except json.decoder.JSONDecodeError:
            import shutil
            shutil.move(self.config_filepath, self.config_filepath+'_error')
            os.remove(self.config_filepath)
        finally:
            self.conform_preferences()

    def save_config(self):
        for name, service in self.services.items():
            self.config['streamservices'][name] = service.config
        with open(self.config_filepath, 'w') as json_file:
            json.dump(self.config, json_file, indent=4)

    def shortcuts(self):
        keyboard.add_hotkey('ctrl+F9', self.create_clip)

    def create_services(self):
        nb = len(SERVICES) or 1
        pool = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=nb) as executor:
            for service in SERVICES.values():
                pool.append(executor.submit(self.create_service, service))
        concurrent.futures.wait(pool, timeout=5)
        self.save_config()

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

    def validate_assignations(self, config, category=None):
        if category:
            config.setdefault(category, {})
        for cat in config:
            if category and cat != category:
                continue
            for service in self.services.values():
                if not service.features['category']:
                    config.setdefault(cat, {}).setdefault(service.name, {})
                    config[cat][service.name] = {'name': '', 'valid': True}
                    continue
                assigned_category = config.get(cat, {}).get(service.name, {}).get('name', '') or cat
                isvalid = config.get(cat, {}).get(service.name, {}).get('valid', False)
                if assigned_category and not isvalid:
                    valid = service.validate_category(assigned_category)
                    config.setdefault(cat, {}).setdefault(service.name, {})
                    config[cat][service.name] = {'name': assigned_category, 'valid': valid}
        return config

    def check_application(self):
        process = tools.getForegroundProcess()
        existing = self.config['appdata'].get(process, '')
        if existing and process!=self.process:
            infos = self.get_informations(process)
            logger.debug(f"title: {infos['title']} | description: {infos['description']} | category: {infos['category']} | tags: {infos['tags']}")
            self.update_channel(infos)
            self.process = process
            return infos

    def get_informations(self, name):
        infos = {}
        infos['tags'] = self.config['appdata'].get(name, {}).get('tags', []) + self.config['base'].get('tags', [])
        infos['title'] = self.config['appdata'].get(name, {}).get('title') or self.config['base'].get('title', '')
        infos['category'] = self.config['appdata'].get(name, {}).get('category') or self.config['base'].get('category', '')
        infos['description'] = self.config['appdata'].get(name, {}).get('description') or self.config['base'].get('description', '')
        for element in ['title', 'description', 'category', 'tags']:
            if self.config['base'].get('forced_' + element):
                infos[element] = self.config['base'].get(element)
        return infos

    def update_servicesinfos(self):
        nb = len(SERVICES) or 1
        pool = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=nb) as executor:
            for service in self.services.values():
                pool.append(executor.submit(service.get_channel_info))
        concurrent.futures.wait(pool, timeout=5)

    def main(self):
        with tools.pause_services(self.config['base']['services']):
            with tools.pause_processes(self.config['base']['processes']):
                obs = subprocess.Popen('obs64.exe --startreplaybuffer', shell=True, cwd="C:\\Program Files (x86)\\obs-studio\\bin\\64bit\\")
                while obs.poll() is None:
                    time.sleep(4)
                    self.check_application()
