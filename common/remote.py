import time
import threading
import lib.bottle as bottle
import common.manager
import common.tools
import logging
logger = logging.getLogger(__name__)

# AJAX? Change background color when there is an update?

class WebRemote():
    def __init__(self):
        super().__init__()
        self.threaded = False
        self.running = False
        self.timer = 1
        self.manager = common.manager.ManageStream()
        self.manager.update_servicesinfos()

    def update_infos(self, infos):
        print('Updated to:', infos)

    @common.tools.threaded
    def start_check_threaded(self):
        self.threaded = False
        self.start_check()
        self.threaded = True

    def check_process(self):
        self.running = True
        while self.running:
            infos = self.manager.check_application()
            if infos:
                self.update_infos(infos)
            time.sleep(self.timer)

    def start_check(self):
        if self.threaded:
            self.start_check_threaded()
        else:
            self.check_process()

    def stop_check(self):
        pass

    def server(self):
        app = bottle.Bottle()

        @app.hook('before_request')
        def strip_path():
            bottle.request.environ['PATH_INFO'] = bottle.request.environ['PATH_INFO'].rstrip('/')

        @app.route('/<filename:path>')
        def staticfiles(filename):
            return bottle.static_file(filename, root='data/theme/')

        @app.route('/')
        def index():
            self.manager.update_servicesinfos()
            action = 'STOP' if self.running else 'START'
            services = {s.name: {'enabled': s.config['enabled'], 'infos': s.infos} for s in self.manager.services.values()}
            return bottle.template('data/theme/remote.tpl', action=action, services=services)

        @app.route('/', method="POST")
        def formhandler():
            action = bottle.request.forms.get('action')
            if action == 'START':
                self.running = True
                self.start_check()
            else:
                self.running = False
                self.stop_check()
            bottle.redirect('/')

        app.run(host='0.0.0.0', port=8080, quiet=False, server='cherrypy')
