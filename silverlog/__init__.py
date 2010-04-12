import os
import re
import json
import time
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
    map.connect('skipped_files', '/api/skipped-files', method='skipped_files')

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
        try:
            log = self.log_set.log_from_id(id)
        except (OSError, IOError), e:
            return json_response(
                dict(error=str(e), log_id=id),
                status='500')
        result = dict(
            path=log.path, group=log.group,
            id=log.id, description=log.description,
            chunks=log.parse_chunks(),
            log_type=log.parser)
        if 'nocontent' not in req.GET:
            result['content'] = log.content()
        return json_response(result)

    def skipped_files(self, req):
        result = dict(
            skipped_files=self.log_set.skipped_files)
        return json_response(result)

NAMES = [
    (r'^SILVER_DIR/apps/(?P<app>[^/]+)/error.log(?:\.(?P<number>\d+))?$',
     ('{{app}}', '{{app}}: error log{{if number}} (backup {{number}}){{endif}}'),
     'silver_error_log'),
    (r'^SILVER_DIR/apps/(?P<app>[^/]+)/(?P<name>.*)(?:\.(?P<number>\d+))?$',
     ('{{app}}', '{{app}}: {{name}}{{if number}} (backup {{number}}){{endif}}'),
     'generic_log'),
    (r'^APACHE_DIR/access.log(?:\.(?P<number>\d+))?$',
     ('system', 'Apache access log{{if number}} (backup {{number}}){{endif}}'),
     'apache_access_log'),
    (r'^APACHE_DIR/error.log(?:\.(?P<number>\d+))?$',
     ('system', 'Apache error log{{if number}} (backup {{number}}){{endif}}'),
     'apache_error_log'),
    (r'^APACHE_DIR/rewrite.log(?:\.(?P<number>\d+))?$',
     ('system', 'Apache rewrite log{{if number}} (backup {{number}}){{endif}}'),
     'apache_rewrite_log'),
    (r'^SILVER_DIR/setup-node.log(?:\.(?P<number>\d+))?',
     ('system', 'silver setup-node log{{if number}} (backup {{number}}){{endif}}'),
     'silver_setup_node_log'),
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
        for pattern, result, parser in NAMES:
            for dirname, dirpath in self.dirs.items():
                pattern = pattern.replace(dirname, dirpath)
            patterns.append((pattern, result, parser))
        for filename in walk_files(self.dirs.values()):
            for pattern, (group, description), parser in patterns:
                match = re.match(pattern, filename)
                if match:
                    vars = match.groupdict()
                    vars['log_set'] = self
                    description = tempita.Template(description).substitute(vars)
                    group = tempita.Template(group).substitute(vars)
                    log = Log(filename, group, description, parser)
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
    def __init__(self, path, group, description, parser):
        self.path = path
        self.group = group
        self.description = description
        self.parser = parser

    def __repr__(self):
        return '<%s %s: %r>' % (
            self.__class__.__name__,
            self.path, self.description)

    def content(self):
        fp = open(self.path)
        c = fp.read()
        fp.close()
        return c

    def parse_chunks(self):
        method = getattr(self, self.parser)
        return method()

    def generic_log(self):
        fp = open(self.path)
        l = []
        for line in fp:
            l.append({'data': line.strip()})
        return l

    def apache_access_log(self):
        fp = open(self.path)
        l = []
        regex = re.compile(
            r'''
            ^
            (?P<ip>-|[0-9.]+?)
              \s+
            - \s+
            - \s+
            \[(?P<date>[^\]]+?)\]
              \s+
            "(?P<method>[A-Z]+)
              \s+
            (?P<path>[^ ]+)
              \s+
            (?P<http_version>[^"]+)"
              \s+
            (?P<response_code>\d+)
              \s+
            (?P<response_bytes>-|\d+)
              \s+
            "(?P<referrer>[^"]*)"
              \s+
            "(?P<user_agent>[^"]*)"
            (?:
              \s+
            (?P<host>[^ ]+)
              \s+
            "(?P<app_name>[^ ]+)"
              \s+
            (?P<milliseconds>\d+)
            )?
            ''', re.VERBOSE)
        for line in fp:
            line = line.strip()
            match = regex.match(line)
            if match:
                data = match.groupdict()
                if data.get('app_name') == '-':
                    data['app_name'] = ''
                data['date'] = self._translate_apache_date(data['date'])
            else:
                data = {}
            data['data'] = line
            l.append(data)
        return l

    @staticmethod
    def _translate_apache_date(date):
        return time.strftime('%B %d, %Y %H:%M:%S', time.strptime(date.split()[0], '%d/%b/%Y:%H:%M:%S'))

    def apache_error_log(self):
        fp = open(self.path)
        l = []
        regex = re.compile(
            r'''
            \[(?P<date>[^\]]+)]
              \s+
            \[(?P<level>[^\]]+)]
              \s
            (?:
              \[client \s+ (?P<remote_addr>[0-9.]+)\]
                \s
            )?
            (?P<message>.*)
            ''', re.VERBOSE)
        last_data = None
        for line in fp:
            line = line.strip()
            match = regex.match(line)
            if match:
                data = match.groupdict()
                if (last_data and data['date'] == last_data.get('date')
                    and data['level'] == last_data.get('level')
                    and data['remote_addr'] == last_data.get('remote_addr')):
                    last_data['data'] += '\n' + line
                    last_data['message'] += '\n' + data['message']
                    continue
            elif last_data:
                last_data['data'] += '\n' + line
                last_data['message'] += '\n' + line
                continue
            else:
                data = {}
            data['data'] = line
            last_data = data
            l.append(data)
        return l

    def silver_setup_node_log(self):
        fp = open(self.path)
        l = []
        rerun = re.compile(
            r'''
            Rerun \s+ setup-node \s+ on \s+ (?P<date>.*)
            ''', re.VERBOSE | re.I)
        run_by = re.compile(
            r'''
            Run \s+ by: \s* (?P<username>.*)
            ''', re.VERBOSE | re.I)
        last_item = {}
        for line in fp:
            line = line.strip()
            last_item.setdefault('data', []).append(line)
            match = rerun.match(line)
            if match:
                last_item.update(match.groupdict())
                continue
            match = run_by.match(line)
            if match:
                last_item.update(match.groupdict())
                continue
            if line == '-'*len(line):
                last_item['data'] = '\n'.join(last_item['data'])
                l.append(last_item)
                last_item = {}
                continue
            last_item.setdefault('messages', []).append(line)
        if last_item:
            last_item['data'] = '\n'.join(last_item['data'])
            l.append(last_item)
        return l

    def apache_rewrite_log(self):
        fp = open(self.path)
        l = []
        regex = re.compile(
            r'''
            ^
            (?P<remote_addr>[0-9\.]+)
              \s+
            - \s+
            - \s+
            \[(?P<date>[^\]]+)\]
              \s+
            \[(?P<request_id>[^\]]+)\]
            \[(?P<request_id2>[^\]]+)\]
              \s+
            \((?P<level>\d+)\)
              \s
            (?P<message>.*)
            ''', re.VERBOSE | re.I)
        last_item = {}
        for line in fp:
            line = line.strip()
            match = regex.match(line)
            if not match:
                l.append(dict(data=line))
                last_item = l[-1]
            else:
                data = match.groupdict()
                data['date'] = self._translate_apache_date(data['date'])
                if not data['message'].startswith('applying pattern'):
                    data['message'] = '  ' + data['message']
                if (last_item
                    and data['remote_addr'] == last_item['remote_addr']
                    and data['date'] == last_item['date']
                    and data['request_id'] == last_item['request_id']):
                    last_item['data'] += '\n' + line
                    last_item['message'] += '\n' + data['message']
                else:
                    data['data'] = line
                    l.append(data)
                    last_item = data
        return l

    @property
    def id(self):
        id = self.path.replace('/', '_').strip('_')
        return id

def json_response(data, **kw):
    return Response(json.dumps(data),
                    content_type='application/json',
                    **kw)
