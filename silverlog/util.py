import urllib
from routes import util

class URLGenerator(util.URLGenerator):

    def __call__(self, *args, **kw):
        params = None
        if 'params' in kw:
            params = kw.pop('params')
        url = super(URLGenerator, self).__call__(*args, **kw)
        if params:
            url += '?'
            if hasattr(params, 'items'):
                params = params.items()
            if not isinstance(params, basestring):
                params = urllib.urlencode(params)
            url += params
        return url
    
