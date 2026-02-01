"""Flask application entry point for Thumbnail Master."""

import io
import logging
from flask import Flask, render_template, jsonify, request, send_file, Response
from werkzeug.exceptions import HTTPException

import config
from indexer import get_db
from parser import get_thumbnail_as_png, DISSECT_AVAILABLE, find_cache_files, get_cache_size_from_filename
from exporter import export_thumbnails_to_zip, export_single_thumbnail

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = config.SECRET_KEY


# Error handlers
@app.errorhandler(HTTPException)
def handle_http_exception(e):
    """Handle HTTP exceptions."""
    return jsonify({
        'error': e.name,
        'message': e.description
    }), e.code


@app.errorhandler(Exception)
def handle_exception(e):
    """Handle generic exceptions."""
    logger.exception("Unhandled exception")
    return jsonify({
        'error': 'Internal Server Error',
        'message': str(e)
    }), 500


# Routes
@app.route('/')
def index():
    """Main gallery view."""
    return render_template('index.html')


@app.route('/api/thumbnails')
def get_thumbnails():
    """
    Get paginated list of thumbnails.
    
    Query params:
        page: Page number (default: 1)
        per_page: Items per page (default: 50)
        size: Filter by cache size (32, 96, 256, 1024, sr, wide)
        search: Search query
        sort: Sort order (newest, oldest, largest, smallest, modified)
        format: Filter by image format (JPEG, PNG, etc.)
        extension: Filter by file extension
        cache_files: Comma-separated list of cache file names to filter by
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', config.THUMBNAILS_PER_PAGE, type=int)
    cache_size = request.args.get('size', '').strip() or None
    search = request.args.get('search', '').strip() or None
    sort = request.args.get('sort', 'newest')
    image_format = request.args.get('format', '').strip() or None
    extension = request.args.get('extension', '').strip() or None
    cache_files_param = request.args.get('cache_files', '').strip()
    
    # Parse cache_files parameter
    cache_files = None
    if cache_files_param:
        cache_files = [f.strip() for f in cache_files_param.split(',') if f.strip()]
        if not cache_files:
            cache_files = None
    
    # Validate per_page (max 1000)
    per_page = min(max(1, per_page), 1000)
    
    db = get_db()
    thumbnails, total = db.get_thumbnails(
        page=page,
        per_page=per_page,
        cache_size=cache_size,
        search=search,
        sort=sort,
        image_format=image_format,
        extension=extension,
        cache_files=cache_files
    )
    
    return jsonify({
        'thumbnails': thumbnails,
        'page': page,
        'per_page': per_page,
        'total': total,
        'total_pages': (total + per_page - 1) // per_page if total > 0 else 0
    })


@app.route('/api/thumbnail/<int:thumb_id>')
def get_thumbnail(thumb_id):
    """Serve individual thumbnail image as PNG."""
    db = get_db()
    data = db.get_thumbnail_data(thumb_id)
    
    if data is None:
        return jsonify({'error': 'Thumbnail not found'}), 404
    
    # Convert to PNG for consistent display
    png_data = get_thumbnail_as_png(data)
    
    return send_file(
        io.BytesIO(png_data),
        mimetype='image/png',
        as_attachment=False,
        download_name=f'thumbnail_{thumb_id}.png'
    )


@app.route('/api/thumbnail/<int:thumb_id>/info')
def get_thumbnail_info(thumb_id):
    """Get thumbnail metadata without image data."""
    db = get_db()
    thumb = db.get_thumbnail_by_id(thumb_id)
    
    if thumb is None:
        return jsonify({'error': 'Thumbnail not found'}), 404
    
    # Remove binary data from response
    thumb_info = {k: v for k, v in thumb.items() if k != 'data'}
    thumb_info['dimensions'] = f"{thumb['width']}x{thumb['height']}" if thumb['width'] and thumb['height'] else None
    
    return jsonify(thumb_info)


@app.route('/api/search')
def search_thumbnails():
    """
    Search thumbnails by metadata.
    
    Query params:
        q: Search query (searches hash, cache_key, entry_hash, extension)
        page: Page number (default: 1)
        per_page: Items per page (default: 50)
    """
    query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', config.THUMBNAILS_PER_PAGE, type=int)
    
    if not query:
        return jsonify({
            'query': query,
            'results': [],
            'total': 0
        })
    
    db = get_db()
    thumbnails, total = db.get_thumbnails(
        page=page,
        per_page=per_page,
        search=query
    )
    
    return jsonify({
        'query': query,
        'results': thumbnails,
        'total': total,
        'page': page,
        'per_page': per_page
    })


@app.route('/api/export', methods=['POST'])
def export_thumbnails():
    """
    Export selected thumbnails as ZIP or single image.
    
    Request body:
        ids: List of thumbnail IDs to export
    """
    data = request.get_json()
    
    if not data or 'ids' not in data:
        return jsonify({'error': 'Missing "ids" in request body'}), 400
    
    ids = data['ids']
    
    if not isinstance(ids, list) or len(ids) == 0:
        return jsonify({'error': 'Invalid or empty "ids" list'}), 400
    
    if len(ids) > config.MAX_EXPORT_COUNT:
        return jsonify({
            'error': f'Too many thumbnails. Maximum is {config.MAX_EXPORT_COUNT}'
        }), 400
    
    db = get_db()
    
    # Single thumbnail - return as PNG
    if len(ids) == 1:
        png_data = export_single_thumbnail(db, ids[0])
        if png_data is None:
            return jsonify({'error': 'Thumbnail not found'}), 404
        
        return send_file(
            io.BytesIO(png_data),
            mimetype='image/png',
            as_attachment=True,
            download_name=f'thumbnail_{ids[0]}.png'
        )
    
    # Multiple thumbnails - return as ZIP
    try:
        zip_data = export_thumbnails_to_zip(db, ids)
        
        return send_file(
            io.BytesIO(zip_data),
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'thumbnails_export_{len(ids)}.zip'
        )
    except Exception as e:
        logger.exception("Export failed")
        return jsonify({'error': str(e)}), 500


@app.route('/api/refresh', methods=['POST'])
def refresh_index():
    """
    Trigger cache re-indexing.
    
    Request body (optional):
        selected_files: List of cache file names to index (indexes all if not provided)
    """
    if not DISSECT_AVAILABLE:
        return jsonify({
            'status': 'error',
            'error': 'dissect.thumbcache library not installed. Run: pip install dissect.thumbcache'
        }), 500
    
    try:
        # Get selected files from request body if provided
        selected_files = None
        data = request.get_json(silent=True)
        if data and 'selected_files' in data:
            selected_files = data['selected_files']
            if isinstance(selected_files, list) and len(selected_files) > 0:
                logger.info(f"Indexing selected files: {selected_files}")
            else:
                selected_files = None
        
        db = get_db()
        logger.info("Starting thumbnail index refresh...")
        count = db.index_all(selected_files=selected_files)
        logger.info(f"Indexed {count} thumbnails")
        
        return jsonify({
            'status': 'success',
            'count': count,
            'message': f'Successfully indexed {count} thumbnails',
            'selected_files': selected_files
        })
    except Exception as e:
        logger.exception("Index refresh failed")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@app.route('/api/stats')
def get_stats():
    """Get dashboard statistics."""
    db = get_db()
    stats = db.get_stats()
    
    # Add library availability info
    stats['dissect_available'] = DISSECT_AVAILABLE
    
    return jsonify(stats)


@app.route('/api/filters')
def get_filters():
    """Get available filter options."""
    db = get_db()
    options = db.get_filter_options()
    return jsonify(options)


@app.route('/api/cache-files')
def get_cache_files():
    """
    Get list of available cache files with their status.
    
    Returns:
        available: List of cache files found on disk with metadata
        indexed: List of cache file names that have been indexed
    """
    from pathlib import Path
    from datetime import datetime
    
    # Get files found on disk
    cache_files = find_cache_files()
    available = []
    
    for file_path in cache_files:
        try:
            stat = file_path.stat()
            available.append({
                'name': file_path.name,
                'size_bytes': stat.st_size,
                'size_mb': round(stat.st_size / (1024 * 1024), 2),
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'cache_size': get_cache_size_from_filename(file_path.name)
            })
        except Exception:
            available.append({
                'name': file_path.name,
                'size_bytes': 0,
                'size_mb': 0,
                'modified': None,
                'cache_size': get_cache_size_from_filename(file_path.name)
            })
    
    # Get indexed files from database
    db = get_db()
    indexed = db.get_indexed_files()
    
    return jsonify({
        'available': available,
        'indexed': indexed
    })


@app.route('/api/health')
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'dissect_available': DISSECT_AVAILABLE
    })


if __name__ == '__main__':
    logger.info(f"Starting Thumbnail Master on http://{config.HOST}:{config.PORT}")
    logger.info(f"dissect.thumbcache available: {DISSECT_AVAILABLE}")
    
    if not DISSECT_AVAILABLE:
        logger.warning("dissect.thumbcache is not installed! Run: pip install dissect.thumbcache")
    
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
