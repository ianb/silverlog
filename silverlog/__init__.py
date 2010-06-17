import os
import re
import json
import time
import tempita
import cPickle as pickle
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
    map.connect('checkpoint', '/api/checkpoint', method='checkpoint')

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
            chunks=log.parse_chunks(self.checkpoint_info(req)),
            log_type=log.parser)
        if 'nocontent' not in req.GET:
            result['content'] = log.content()
        return json_response(result)

    def skipped_files(self, req):
        result = dict(
            skipped_files=self.log_set.skipped_files)
        return json_response(result)

    def checkpoint(self, req):
        if req.method == 'POST':
            id = self.make_new_checkpoint()
            return json_response(dict(checkpoint=id))
        elif req.method == 'GET':
            return json_response(dict(
                checkpoints=[c for c in self.checkpoint_list()]))

    def make_new_checkpoint(self):
        date = time.gmtime()
        timestamp = time.strftime('%Y%m%dT%H%M%S', date)
        date = translate_date(date)
        fn = self.checkpoint_filename(timestamp)
        data = {}
        for group in self.log_set.logs.values():
            for log_filename in group.keys():
                size = os.path.getsize(log_filename)
                data[log_filename] = size
        fp = open(fn, 'wb')
        pickle.dump(data, fp)
        fp.close()
        return dict(id=timestamp, date=date)

    def checkpoint_list(self):
        result = []
        for name in os.listdir(self.checkpoint_dir):
            base, ext = os.path.splitext(name)
            if ext != '.checkpoint':
                continue
            date = time.strptime(base, '%Y%m%dT%H%M%S')
            result.append(dict(id=base, date=translate_date(date)))
        return result

    def checkpoint_info(self, req):
        if not req.GET.get('checkpoint'):
            return None
        fn = self.checkpoint_filename(req.GET['checkpoint'])
        fp = open(fn, 'rb')
        data = pickle.load(fp)
        fp.close()
        return data

    def checkpoint_filename(self, id):
        assert re.search(r'^[a-zA-Z0-9]+$', id)
        path = os.path.join(self.checkpoint_dir, id+'.checkpoint')
        if not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))
        return path

    @property
    def checkpoint_dir(self):
        dir = os.path.join(os.environ['CONFIG_FILES'], 'checkpoints')
        if not os.path.exists(dir):
            os.makedirs(dir)
        return dir

NAMES = [
    (r'^SILVER_DIR/apps/(?P<app>[^/]+)/errors\.log(?:\.(?P<number>\d+))?$',
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

    def parse_chunks(self, checkpoint_info):
        place = None
        if checkpoint_info and checkpoint_info.get(self.path):
            place = checkpoint_info[self.path]
        fp = open(self.path)
        try:
            if place:
                print 'seeking %s to %s' % (self.path, place)
                fp.seek(place)
            else:
                print 'No seek on %s' % self.path
            method = getattr(self, self.parser)
            result = method(fp)
            #result['offset'] = place
            return result
        finally:
            fp.close()

    def generic_log(self, fp):
        l = []
        for line in fp:
            l.append({'data': line.strip()})
        return l

    def apache_access_log(self, fp):
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
                data['date'] = translate_apache_date(data['date'])
            else:
                data = {}
            data['data'] = line
            l.append(data)
        return l

    def apache_error_log(self, fp):
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

    def silver_setup_node_log(self, fp):
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
            if line == '-' * len(line):
                last_item['data'] = '\n'.join(last_item['data'])
                l.append(last_item)
                last_item = {}
                continue
            last_item.setdefault('messages', []).append(line)
        if last_item:
            last_item['data'] = '\n'.join(last_item['data'])
            l.append(last_item)
        return l

    def apache_rewrite_log(self, fp):
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
                data['date'] = translate_apache_date(data['date'])
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

    def silver_error_log(self, fp):
        l = []
        start_regex = re.compile(
            r'''
            Errors \s+ for \s+ request \s+
            (?P<method>[A-Z]+) \s+
            (?P<path>[^\s]+) \s+
            \((?P<date>[^)]*)\):
            ''', re.VERBOSE)
        end_regex = re.compile(
            r'''Finish errors for request''')
        for line in fp:
            line = line.rstrip()
            match = start_regex.match(line)
            if match:
                l.append(match.groupdict())
                try:
                    l[-1]['date'] = translate_date(time.strptime(l[-1]['date'].split(',')[0], '%Y-%m-%d %H:%M:%S'))
                except ValueError:
                    # Just don't convert if it's weird
                    pass
                l[-1]['lines'] = []
                continue
            match = end_regex.match(line)
            if match:
                # Well, I guess we don't care
                continue
            if not l:
                l.append(dict(method='unknown',
                              path='unknown',
                              date=None,
                              lines=[]))
            l[-1]['lines'].append(line)
        for item in l:
            item['message'] = '\n'.join(item.pop('lines'))
        return l

    @property
    def id(self):
        id = self.path.replace('/', '_').strip('_')
        return id

def json_response(data, **kw):
    return Response(json.dumps(data),
                    content_type='application/json',
                    **kw)

def translate_apache_date(date):
    return translate_date(time.strptime(date.split()[0], '%d/%b/%Y:%H:%M:%S'))

def translate_date(date):
    return time.strftime('%B %d, %Y %H:%M:%S', date)
