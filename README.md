# Thumbnail Master

A web-based application for viewing, browsing, searching, and exporting thumbnails from Windows Explorer's thumbnail cache files.

## Features

- **Browse Thumbnails**: View all cached thumbnails in a responsive grid layout
- **Filter by Size**: Filter thumbnails by cache size (32x32, 96x96, 256x256, 1024px, etc.)
- **Search**: Search thumbnails by hash or cache key
- **Sort Options**: Sort by newest, oldest, largest, or smallest
- **Export**: Export individual thumbnails or bulk export as ZIP
- **Select Mode**: Multi-select thumbnails for batch operations
- **Metadata Display**: View detailed metadata for each thumbnail

## Requirements

- Python 3.8 or higher
- Windows OS (for accessing thumbnail cache)

## Installation

1. **Clone or navigate to the project directory:**
   ```bash
   cd path/to/thumbnail-master
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. **Start the application:**
   ```bash
   python app.py
   ```

2. **Open your browser and navigate to:**
   ```
   http://127.0.0.1:5000
   ```

3. **Click "Refresh" to scan and index your thumbnail cache**

## Project Structure

```
Thumbnail Master/
├── app.py              # Flask application entry point
├── parser.py           # Thumbcache file parsing logic
├── indexer.py          # SQLite database indexing
├── exporter.py         # Export functionality
├── config.py           # Configuration settings
├── requirements.txt    # Python dependencies
├── README.md           # This file
├── static/
│   ├── css/
│   │   └── style.css   # Custom styles
│   └── js/
│       └── app.js      # Frontend JavaScript
└── templates/
    └── index.html      # Main gallery page
```

## Configuration

Edit `config.py` to customize settings:

- `DEFAULT_CACHE_PATH`: Location of thumbnail cache files (default: `%LocalAppData%\Microsoft\Windows\Explorer\`)
- `HOST`: Server host (default: `127.0.0.1`)
- `PORT`: Server port (default: `5000`)
- `THUMBNAILS_PER_PAGE`: Items per page (default: `50`)
- `MAX_EXPORT_COUNT`: Maximum thumbnails per export (default: `1000`)

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main gallery view |
| `/api/thumbnails` | GET | Get paginated thumbnails |
| `/api/thumbnail/<id>` | GET | Get thumbnail image |
| `/api/thumbnail/<id>/info` | GET | Get thumbnail metadata |
| `/api/search?q=<query>` | GET | Search thumbnails |
| `/api/export` | POST | Export thumbnails |
| `/api/refresh` | POST | Re-index thumbnail cache |
| `/api/stats` | GET | Get statistics |
| `/api/health` | GET | Health check |

## Query Parameters for `/api/thumbnails`

- `page`: Page number (default: 1)
- `per_page`: Items per page (default: 50, max: 100)
- `size`: Filter by cache size (32, 96, 256, 1024, sr, wide, exif)
- `search`: Search query
- `sort`: Sort order (newest, oldest, largest, smallest)

## Thumbnail Cache Locations

Windows stores thumbnail caches in:
```
%LocalAppData%\Microsoft\Windows\Explorer\
```

Common cache files:
- `thumbcache_32.db` - 32x32 thumbnails
- `thumbcache_96.db` - 96x96 thumbnails
- `thumbcache_256.db` - 256x256 thumbnails
- `thumbcache_1024.db` - 1024px thumbnails
- `thumbcache_sr.db` - Super resolution thumbnails
- `thumbcache_wide.db` - Wide format thumbnails
- `thumbcache_exif.db` - EXIF-based thumbnails

## Troubleshooting

### "dissect.thumbcache is not installed"

Run:
```bash
pip install dissect.thumbcache
```

### No thumbnails found

1. Make sure Windows Explorer has generated thumbnails by browsing folders with images
2. Check that the cache path in `config.py` is correct
3. Verify cache files exist in `%LocalAppData%\Microsoft\Windows\Explorer\`

### Permission errors

Run the application with administrator privileges if you encounter permission errors accessing cache files.

## Dependencies

- **Flask**: Web framework
- **dissect.thumbcache**: Windows thumbnail cache parser
- **Pillow**: Image processing
- **Werkzeug**: WSGI utilities

## License

This project is for educational and personal use.

## Security Notes

- The application runs on localhost only (`127.0.0.1`)
- Read-only access to thumbnail cache files
- No external network connections required
- Temporary export files are cleaned up automatically
