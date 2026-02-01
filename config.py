"""Configuration settings for Thumbnail Master.

Environment Variables:
    FLASK_DEBUG: Set to '1' or 'true' to enable debug mode (default: False)
    FLASK_HOST: Server host (default: 127.0.0.1)
    FLASK_PORT: Server port (default: 5000)
    SECRET_KEY: Flask secret key (auto-generated if not set)
"""

import os
from pathlib import Path

# Default thumbcache location (uses Windows environment variable)
DEFAULT_CACHE_PATH = Path(os.path.expandvars(r'%LocalAppData%\Microsoft\Windows\Explorer'))

# Database settings (stored locally, excluded from version control)
DATABASE_PATH = Path(__file__).parent / 'thumbnails.db'

# Flask settings (configurable via environment variables)
DEBUG = os.environ.get('FLASK_DEBUG', '').lower() in ('1', 'true', 'yes')
HOST = os.environ.get('FLASK_HOST', '127.0.0.1')
PORT = int(os.environ.get('FLASK_PORT', '5000'))
SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(24).hex()

# Pagination
THUMBNAILS_PER_PAGE = 50

# Supported thumbcache files
THUMBCACHE_FILES = [
    'thumbcache_32.db',
    'thumbcache_96.db',
    'thumbcache_256.db',
    'thumbcache_1024.db',
    'thumbcache_sr.db',
    'thumbcache_wide.db',
    'thumbcache_exif.db',
    'thumbcache_wide_alternate.db',
]

# Export settings
EXPORT_TEMP_DIR = Path(__file__).parent / 'temp_exports'
MAX_EXPORT_COUNT = 1000
