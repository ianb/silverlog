from silverlog import Application
import os

if os.environ.get('SILVER_VERSION', '').startswith('silverlining/'):
    application = Application()
else:
    base = os.path.join(os.path.dirname(__file__), 'tests', 'test-logs')
    application = Application(
        {'SILVER_DIR': os.path.join(base, 'silverlining'),
         'APACHE_DIR': os.path.join(base, 'apache2'),
         })

