# coding: utf-8
import os
import sys
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
            self.conform_preferences()
            self.load_database()
            socket.setdefaulttimeout(int(self.config['base']['timeout']))

    def conform_preferences(self):
        template = {
        "streamservices": {service.Main.name: service.Main.default_config() for service in SERVICES.values()},
        "appdata": {},
        "base": {
            "title": "",
            "description": "",
            "port": 8080,
            "autostart": False,
            "starttray": False,
            "checktimer": "60",
            "reload": "5",
            "timeout": "10",
            "processes": [],
            "category": "",
            "services": [],
            "tags": [],
            "forced_category": False,
            "forced_title": False,
            "forced_description": False,
            "forced_tags": False
            },
        "assignations": {},
        "shortcuts": {
            "create_clip": "Ctrl+F9",
            "create_marker": "Ctrl+F10"
            }
        }
        for key, value in template.items():
            self.config.setdefault(key, value)
            for k, v in value.items():
                self.config[key].setdefault(k, v)

    def load_config(self, path='', backup=True):
        path = path or self.config_filepath
        config = tools.load_json(path, backup)
        if config:
            self.config = config or {}
            return config
        return config

    def save_config(self, path=''):
        path = path or self.config_filepath
        for name, service in self.services.items():
            self.config['streamservices'][name] = service.config
        try:
            return tools.save_json(self.config, path)
        except:
            logger.critical(traceback.print_exc())
            logging.error(self.config)
            return False

    def load_credentials(self, path=''):
        path = path or self.config_filepath.replace('settings.json', 'credentials.json')
        config = tools.load_json(path, backup=False)
        for service, values in config.items() or {}:
            logger.info('Loading credentials for "{}" service'.format(service))
            for k, v in values.items():
                self.config['streamservices'][service][k] = v
        return config

    def load_database(self, path=''):
        path = path or self.config_filepath.replace('settings.json', 'database.json')
        self.database = tools.load_json(path) or {}
        return self.database

    def import_database(self, path=''):
        database = tools.load_json(path)
        tools.merge_dict(self.database, database)
        tools.save_json(self.database, self.config_filepath.replace('settings.json', 'database.json'))

    def export_database(self, path=''):
        keys = list(set(list(self.config['assignations'].keys()) + list(self.config['appdata'].keys())))
        database = {}
        for process in keys:
            database[process] = {}
            appdata = self.config['appdata'].get(process)
            assignations = self.config['assignations'].get(process)
            if appdata:
                database[process]['appdata'] = {'path': appdata['path'], 'category': appdata['category']}
            if assignations:
                [assignations[i].pop('valid', None) for i in assignations]
                database[process]['assignations'] = assignations
        tools.save_json(database, path)

    def set_loglevel(self, level=''):
        level = logging.getLevelName(level.upper())
        for key in logging.Logger.manager.loggerDict:
            if any(word in key for word in ['common.', 'services.']):
                logging.getLogger(key).setLevel(level)
            else:
                logging.getLogger(key).setLevel(logging.WARNING)

    def add_process(self, process):
        template = {
            "path": {
                "win32": "",
                "darwin": "",
                "linux": ""
                },
            "category": "",
            "tags": [],
            "title": "",
            "description": ""
        }
        if self.database.get(process):
            self.config['appdata'][process] = {**template, **self.database[process].get('appdata', {})}
            self.config['assignations'][process] = self.database[process].get('assignations', {})
        else:
            self.config['appdata'][process] = template

    def rename_process(self, oldprocess, newprocess):
        try:
            self.config['appdata'][newprocess] = self.config['appdata'].pop(oldprocess)
        except KeyError:
            self.add_process(newprocess)

    def remove_process(self, process):
        try:
            self.config['appdata'].pop(process)
        except KeyError:
            pass

    def create_services(self, force=False, threading=False):
        if force:
            self.services = {}
        if threading:
            nb = len(SERVICES) or 1
            pool = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=nb) as executor:
                for service in SERVICES:
                    if service not in self.services:
                        pool.append(executor.submit(self.create_service, service, self.config['streamservices'].get(service), force=force))
            concurrent.futures.wait(pool, timeout=5)
            for service in pool:
                if service.result():
                    self.services[service.result().name] = service.result()
        else:
            for service in SERVICES:
                if service not in self.services:
                    result = self.create_service(service, self.config['streamservices'].get(service), force=force)
                    if result:
                        self.services[service] = result

    def create_service(self, service, config, force=False):
        try:
            if force or config['enabled']:
                service = SERVICES[service].Main(config)
                logger.info('Created service "{}"'.format(service.name))
                return service
        except (socket.timeout, SERVICES[service].Timeout):
            logger.error('Timeout when creating service {}'.format(service))
            self.config['streamservices'][service]['authorization'] = {}
            return False
        except:
            return False

    def deactivate_service(self, service):
        self.services.pop(service, None)

    def create_clip(self):
        for service in self.services.values():
            service.create_clip()

    def create_marker(self):
        for service in self.services.values():
            service.create_marker()

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
                if service.features['category']:
                    assigned_category = config.get(cat, {}).get(service.name, {}).get('name', '') or cat
                    isvalid = config.get(cat, {}).get(service.name, {}).get('valid', None)
                    if assigned_category and not isvalid:
                        valid = service.validate_category(assigned_category)
                        config[cat][service.name] = {'name': assigned_category, 'valid': valid}
        return config

    def is_validcategories(self, category):
        isvalid = []
        for i in self.config['assignations'].get(category, {}).values():
            if i in list(self.services.keys()):
                isvalid += i.get('valid', False)
        return all(isvalid)

    def get_processfrompath(self, path, platform=None):
        if not platform:
            platform = sys.platform
        for process, values in self.config['appdata'].items():
            pathlist = values['path'][platform].lower().split(',')
            if any(proc in path.lower() for proc in pathlist):
                return process
        return ''

    def check_application(self):
        processpath = tools.getForegroundProcess()
        process = self.get_processfrompath(processpath)
        existing = self.config['appdata'].get(process, '')
        if existing and process!=self.process:
            infos = self.get_informations(process)
            logger.info(f"title: {infos['title']} | description: {infos['description']} | category: {infos['category']} | tags: {infos['tags']}")
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
