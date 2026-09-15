import os
from .base import *

DEBUG = True

ALLOWED_HOSTS = ['*']

# Use standard staticfiles storage in development to ease hot reloading
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

# Allow database override via DATABASE_URL if someone tests with local postgres
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    import dj_database_url
    DATABASES['default'] = dj_database_url.parse(DATABASE_URL)
