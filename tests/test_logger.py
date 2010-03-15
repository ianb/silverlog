from webtest import TestApp
import os

fn = os.path.join(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))), 'silver-runner.py')
ns = {'__file__': fn}
execfile(fn, ns)
wsgi_app = ns['application']
app = TestApp(wsgi_app)

def test_app():
    assert wsgi_app.log_set.dirs
    resp = app.get('/')
    resp.mustcontain(
        'setup-node.log', 'rewrite.log')
    resp = resp.click(href=r'/view/system\?path=.*rewrite\.log')
    print resp

if __name__ == '__main__':
    test_app()
    
