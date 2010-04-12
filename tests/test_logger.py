from webtest import TestApp
import os

fn = os.path.join(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))), 'silver-runner.py')
ns = {'__file__': fn}
execfile(fn, ns)
wsgi_app = ns['application']
app = TestApp(wsgi_app)

here_id = os.path.dirname(os.path.dirname(__file__)).replace('/', '_').strip('_')

def test_app():
    resp = app.get('/api/list-logs')
    assert resp.json
    resp = app.get('/api/log/%s_tests_test-logs_apache2_access.log'
                   % here_id)
    assert resp.json
    import pprint
    pprint.pprint(resp.json['chunks'][0])
    assert 0

if __name__ == '__main__':
    test_app()
