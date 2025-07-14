"""
WSGI config for Estoque project.
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Estoque.settings')

application = get_wsgi_application()