import time
import threading
import bottle
import common.manager
import common.tools

# AJAX? Change background color when there is an update?

class WebRemote():
    def __init__(self):
        super().__init__()
        self.threaded = False
        self.running = False
        self.manager = common.manager.ManageStream()

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
            time.sleep(1)
            if infos:
                self.update_infos(infos)

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

        @app.route('/')
        def index():
            action= 'Stop' if self.running else 'Run'
            return bottle.template('data/theme/remote.tpl', action=action, services=self.manager.services)

        @app.route('/', method="POST")
        def formhandler():
            action = bottle.request.forms.get('action')
            if action == 'Run':
                self.running = True
                self.start_check()
            else:
                self.running = False
                self.stop_check()
            action = 'Stop' if self.running else 'Run'
            return bottle.template('data/theme/remote.tpl', action=action, services=self.manager.services)
        app.run(quiet=True)
