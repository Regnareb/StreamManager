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
    def check_process_threaded(self):
        self.threaded = False
        self.check_process()
        self.threaded = True

    def check_process(self):
        if self.threaded:
            self.check_process_threaded()
        while self.running:
            infos = self.manager.check_application()
            time.sleep(1)
            if infos:
                self.update_infos(infos)

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
                self.check_process()
            else:
                self.running = False
            action= 'Stop' if self.running else 'Run'
            return bottle.template('data/theme/remote.tpl', action=action, services=self.manager.services)
        app.run(quiet=True)
