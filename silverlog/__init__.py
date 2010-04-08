import os
import re
import json
import tempita
from webob.dec import wsgify
from webob import exc
from webob import Response
from routes import Mapper
from silverlog.util import URLGenerator

class Application(object):

    map = Mapper()
    map.connect('list_logs', '/api/list-logs', method='list_logs')
    map.connect('log_view', '/api/log/{id}', method='log_view')

    def __init__(self, dirs=None, template_base=None):
        if template_base:
            self.template_base = template_base
        if dirs is None:
            dirs = DEFAULT_DIRS
        self.log_set = LogSet(dirs)
        self.log_set.read()

    @wsgify
    def __call__(self, req):
        results = self.map.routematch(environ=req.environ)
        print results, req.path_info
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

    def list_logs(self, req):
        result = {}
        items = result['logs'] = []
        for path, logs in sorted(self.log_set.logs.iteritems()):
            for log in logs.values():
                items.append(dict(path=path, group=log.group,
                                  id=log.id, description=log.description))
        return json_response(result)

    def log_view(self, req, id):
        log = self.log_set.log_from_id(id)
        result = dict(
            path=log.path, group=log.group,
            id=log.id, description=log.description,
            content=log.content())
        return json_response(result)

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

    def log_from_id(self, id):
        path = '/' + id.replace('_', '/')
        for group, items in self.logs.iteritems():
            if path in items:
                return items[path]
        raise LookupError("No log with the path %r" % path)

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

    @property
    def id(self):
        id = self.path.replace('/', '_').strip('_')
        return id

def json_response(data):
    return Response(json.dumps(data),
                    content_type='application/json')
