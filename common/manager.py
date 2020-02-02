# coding: utf-8
import os
import time
import json
import socket
import atexit
import logging
import traceback
import subprocess
import concurrent.futures

import common.tools as tools

logger = logging.getLogger(__name__)

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
        "assignations": {},
        "shortcuts": {
            "createclip": "Ctrl+F9"
            }
        }
        for key, value in template.items():
            self.config.setdefault(key, value)
            for k, v in value.items():
                self.config[key].setdefault(k, v)

    def load_config(self):
        self.config = tools.load_json(self.config_filepath) or {}
        self.conform_preferences()

    def load_credentials(self, path=''):
        if not path:
            path = self.config_filepath.replace('settings.json', 'credentials.json')
        config = tools.load_json(path) or {}
        for service, values in config.items():
            logger.info('Loading credentials for "{}" service'.format(service))
            for k, v in values.items():
                self.config['streamservices'][service][k] = v

    def save_config(self):
        for name, service in self.services.items():
            self.config['streamservices'][name] = service.config
        try:
            with open(self.config_filepath, 'w') as json_file:
                json.dump(self.config, json_file, indent=4)
            return True
        except:
            logger.critical(traceback.print_exc())
            logging.error(self.config)
            return False

    def create_services(self, force=False, threading=True):
        if threading:
            nb = len(SERVICES) or 1
            pool = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=nb) as executor:
                for service in SERVICES:
                    pool.append(executor.submit(self.create_service, service, self.config['streamservices'].get(service), force=force))
            concurrent.futures.wait(pool, timeout=5)
            for service in pool:
                if service.result():
                    self.services[service.result().name] = service.result()
        else:
            for service in SERVICES:
                result = self.create_service(service, self.config['streamservices'].get(service), force=force)
                if result:
                    self.services[service] = result

    def create_service(self, service, config, force=False):
        try:
            if force:
                self.services.pop(service, None)
            if force or config.get('enabled', False) and service not in self.services:
                service = SERVICES[service].Main(config)
                logger.info('Created service "{}"'.format(service.name))
                return service
        except (socket.timeout, SERVICES[service].Timeout):
            logger.error('Timeout when creating service {}'.format(service))
            self.config['streamservices'][service]['authorization'] = {}
            return False

    def deactivate_service(self, service):
        self.services.pop(service, None)

    def create_clip(self):
        for service in self.services.values():
            service.create_clip()

    def update_channel(self, infos):
        for service in self.services.values():
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
