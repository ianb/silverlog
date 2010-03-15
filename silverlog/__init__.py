import os
import re
import tempita
from webob.dec import wsgify
from webob import exc
from webob import Response
from routes import Mapper
from silverlog.util import URLGenerator

class Application(object):

    map = Mapper()
    map.connect('index', '/', method='index')
    map.connect('view', '/view/{group}', method='view')
    template_base = os.path.join(os.path.dirname(__file__), 'templates')

    def __init__(self, dirs=None, template_base=None):
        if template_base:
            self.template_base = template_base
        if dirs is None:
            dirs = DEFAULT_DIRS
        self.log_set = LogSet(dirs)
        self.log_set.read()

    def render(self, template_name, req, title, **kw):
        kw['req'] = req
        kw['title'] = title
        kw['app'] = self
        kw['log_set'] = self.log_set
        tmpl = tempita.HTMLTemplate.from_filename(
            os.path.join(self.template_base, template_name + '.html'),
            default_inherit=os.path.join(self.template_base, 'base.html'))
        return tmpl.substitute(kw)

    @wsgify
    def __call__(self, req):
        results = self.map.routematch(environ=req.environ)
        if not results:
            return exc.HTTPNotFound()
        match, route = results
        if match:
            link = URLGenerator(self.map, req.environ)
            req.environ['wsgiorg.routing_args'] = ((), match)
        method = match['method']
        kwargs = match.copy()
        del kwargs['method']
        req.link = link
        return getattr(self, method)(req, **kwargs)

    def index(self, req):
        return Response(
            self.render('index', req, 'Index of logs'))

    def view(self, req, group):
        path = req.GET['path']
        log = self.log_set.logs[group][path]
        return Response(
            self.render('view', req, 'Viewing %s' % log.description,
                        log=log))

NAMES = [
    (r'^SILVER_DIR/apps/(?P<app>[^/]+)/stderr.log$',
     ('{{app}}', '{{app}}: stderr')),
    (r'^SILVER_DIR/apps/(?P<app>[^/]+)/(?P<name>.*)$',
     ('{{app}}', '{{app}}: {{name}}')),
    (r'^APACHE_DIR/access.log$',
     ('system', 'Apache access log')),
    (r'^APACHE_DIR/error.log$',
     ('system', 'Apache error log')),
    (r'^APACHE_DIR/rewrite.log$',
     ('system', 'Apache rewrite log')),
    (r'^SILVER_DIR/setup-node.log',
     ('system', 'silver setup-node log')),
    ]

DEFAULT_DIRS = {
    'SILVER_DIR': '/var/log/silverlining',
    'APACHE_DIR': '/var/log/apache2',
    }

class LogSet(object):

    def __init__(self, dirs):
        self.dirs = dirs
        self.logs = {}
        self.skipped_files = []

    def read(self):
        self.logs = {}
        patterns = []
        for pattern, result in NAMES:
            for dirname, dirpath in self.dirs.items():
                pattern = pattern.replace(dirname, dirpath)
            patterns.append((pattern, result))
        for filename in walk_files(self.dirs.values()):
            for pattern, (group, description) in patterns:
                match = re.match(pattern, filename)
                if match:
                    vars = match.groupdict()
                    vars['log_set'] = self
                    description = tempita.Template(description).substitute(vars)
                    group = tempita.Template(group).substitute(vars)
                    log = Log(filename, group, description)
                    self.logs.setdefault(group, {})[filename] = log
                    break
            else:
                ## FIXME: should log something about ignoring the log
                self.skipped_files.append(filename)

def walk_files(dirs):
    for dir in dirs:
        for dirpath, dirnames, filenames in os.walk(dir):
            for filename in filenames:
                filename = os.path.join(dirpath, filename)
                yield filename

class Log(object):
    def __init__(self, path, group, description):
        self.path = path
        self.group = group
        self.description = description
        
    def __repr__(self):
        return '<%s %s: %r>' % (
            self.__class__.__name__,
            self.path, self.description)

    def content(self):
        fp = open(self.path)
        c = fp.read()
        fp.close()
        return c
