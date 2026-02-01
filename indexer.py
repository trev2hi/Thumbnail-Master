"""Database indexer for thumbnail cache entries."""

import sqlite3
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from contextlib import contextmanager

import config
from parser import parse_all_thumbcaches, ThumbnailEntry, get_cache_stats


class ThumbnailDatabase:
    """SQLite database manager for thumbnail indexing."""
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or config.DATABASE_PATH
        self._local = threading.local()
        self._init_db()
    
    @property
    def _connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection
    
    @contextmanager
    def _cursor(self):
        """Context manager for database cursor."""
        cursor = self._connection.cursor()
        try:
            yield cursor
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise
        finally:
            cursor.close()
    
    def _init_db(self):
        """Initialize the database schema."""
        with self._cursor() as cursor:
            # Drop old table if schema changed (for development)
            # cursor.execute('DROP TABLE IF EXISTS thumbnails')
            
            # Main thumbnails table with all metadata
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS thumbnails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cache_file TEXT NOT NULL,
                    cache_key TEXT NOT NULL,
                    cache_size TEXT,
                    width INTEGER,
                    height INTEGER,
                    data_size INTEGER,
                    hash TEXT,
                    data BLOB NOT NULL,
                    -- Additional metadata fields
                    entry_hash TEXT,
                    extension TEXT,
                    data_checksum TEXT,
                    header_checksum TEXT,
                    image_format TEXT,
                    image_mode TEXT,
                    last_modified TEXT,
                    flags INTEGER,
                    -- Indexing metadata
                    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(cache_file, cache_key)
                )
            ''')
            
            # Add columns if they don't exist (for upgrading existing databases)
            existing_columns = set()
            cursor.execute('PRAGMA table_info(thumbnails)')
            for row in cursor.fetchall():
                existing_columns.add(row[1])
            
            new_columns = [
                ('entry_hash', 'TEXT'),
                ('extension', 'TEXT'),
                ('data_checksum', 'TEXT'),
                ('header_checksum', 'TEXT'),
                ('image_format', 'TEXT'),
                ('image_mode', 'TEXT'),
                ('last_modified', 'TEXT'),
                ('flags', 'INTEGER'),
            ]
            
            for col_name, col_type in new_columns:
                if col_name not in existing_columns:
                    cursor.execute(f'ALTER TABLE thumbnails ADD COLUMN {col_name} {col_type}')
            
            # Indexes for faster searches
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_thumbnails_cache_file 
                ON thumbnails(cache_file)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_thumbnails_cache_size 
                ON thumbnails(cache_size)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_thumbnails_hash 
                ON thumbnails(hash)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_thumbnails_data_size 
                ON thumbnails(data_size)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_thumbnails_extension 
                ON thumbnails(extension)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_thumbnails_image_format 
                ON thumbnails(image_format)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_thumbnails_last_modified 
                ON thumbnails(last_modified)
            ''')
            
            # Metadata table for tracking indexing status
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
    
    def clear_index(self, cache_files: Optional[List[str]] = None):
        """
        Clear indexed thumbnails.
        
        Args:
            cache_files: Optional list of cache file names to clear.
                        If None, clears all indexed data.
        """
        with self._cursor() as cursor:
            if cache_files:
                # Only clear thumbnails from specific files
                placeholders = ','.join(['?' for _ in cache_files])
                cursor.execute(f'DELETE FROM thumbnails WHERE cache_file IN ({placeholders})', cache_files)
            else:
                # Clear everything
                cursor.execute('DELETE FROM thumbnails')
                cursor.execute('DELETE FROM metadata')
    
    def index_thumbnail(self, entry: ThumbnailEntry) -> int:
        """
        Index a single thumbnail entry.
        
        Returns the row ID of the inserted/updated entry.
        """
        with self._cursor() as cursor:
            cursor.execute('''
                INSERT OR REPLACE INTO thumbnails 
                (cache_file, cache_key, cache_size, width, height, data_size, hash, data,
                 entry_hash, extension, data_checksum, header_checksum, image_format, 
                 image_mode, last_modified, flags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                entry.cache_file,
                entry.cache_key,
                entry.cache_size,
                entry.width,
                entry.height,
                entry.data_size,
                entry.hash,
                entry.data,
                entry.entry_hash,
                entry.extension,
                entry.data_checksum,
                entry.header_checksum,
                entry.image_format,
                entry.image_mode,
                entry.last_modified,
                entry.flags,
            ))
            return cursor.lastrowid
    
    def index_all(self, cache_path: Optional[Path] = None, 
                  progress_callback=None,
                  selected_files: Optional[List[str]] = None) -> int:
        """
        Index all thumbnails from cache files.
        
        Args:
            cache_path: Path to thumbnail cache directory
            progress_callback: Optional callback(current, total) for progress
            selected_files: Optional list of cache file names to index.
                           If None, all files are indexed.
            
        Returns:
            Number of thumbnails indexed
        """
        # Clear existing index (only for selected files if specified)
        self.clear_index(selected_files)
        
        count = 0
        for entry in parse_all_thumbcaches(cache_path, selected_files=selected_files):
            self.index_thumbnail(entry)
            count += 1
            
            if progress_callback and count % 100 == 0:
                progress_callback(count, None)
        
        # Update metadata
        self._set_metadata('last_indexed', datetime.now().isoformat())
        self._set_metadata('thumbnail_count', str(count))
        
        # Store selected files in metadata for reference
        if selected_files is not None:
            self._set_metadata('selected_files', ','.join(selected_files))
        else:
            self._set_metadata('selected_files', '')
        
        return count
    
    def _set_metadata(self, key: str, value: str):
        """Set a metadata value."""
        with self._cursor() as cursor:
            cursor.execute('''
                INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)
            ''', (key, value))
    
    def _get_metadata(self, key: str) -> Optional[str]:
        """Get a metadata value."""
        with self._cursor() as cursor:
            cursor.execute('SELECT value FROM metadata WHERE key = ?', (key,))
            row = cursor.fetchone()
            return row['value'] if row else None
    
    def get_thumbnail_count(self) -> int:
        """Get total number of indexed thumbnails."""
        with self._cursor() as cursor:
            cursor.execute('SELECT COUNT(*) as count FROM thumbnails')
            row = cursor.fetchone()
            return row['count'] if row else 0
    
    def get_thumbnail_by_id(self, thumb_id: int) -> Optional[Dict[str, Any]]:
        """Get a thumbnail by its ID (including all metadata)."""
        with self._cursor() as cursor:
            cursor.execute('''
                SELECT id, cache_file, cache_key, cache_size, width, height, 
                       data_size, hash, data, entry_hash, extension, data_checksum,
                       header_checksum, image_format, image_mode, last_modified, 
                       flags, indexed_at
                FROM thumbnails WHERE id = ?
            ''', (thumb_id,))
            row = cursor.fetchone()
            
            if row:
                return dict(row)
            return None
    
    def get_thumbnail_data(self, thumb_id: int) -> Optional[bytes]:
        """Get just the thumbnail data by ID."""
        with self._cursor() as cursor:
            cursor.execute('SELECT data FROM thumbnails WHERE id = ?', (thumb_id,))
            row = cursor.fetchone()
            return row['data'] if row else None
    
    def get_thumbnails(self, page: int = 1, per_page: int = 50,
                       cache_size: Optional[str] = None,
                       search: Optional[str] = None,
                       sort: str = 'newest',
                       image_format: Optional[str] = None,
                       extension: Optional[str] = None,
                       cache_files: Optional[List[str]] = None) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get paginated list of thumbnails.
        
        Args:
            page: Page number (1-indexed)
            per_page: Items per page
            cache_size: Filter by cache size (e.g., "256", "1024")
            search: Search query for hash/cache_key
            sort: Sort order ("newest", "oldest", "largest", "smallest", "modified")
            image_format: Filter by image format (JPEG, PNG, etc.)
            extension: Filter by file extension
            cache_files: Filter by specific cache file names
            
        Returns:
            Tuple of (list of thumbnail dicts without data, total count)
        """
        # Build query
        conditions = []
        params = []
        
        if cache_size:
            conditions.append('cache_size = ?')
            params.append(cache_size)
        
        if image_format:
            conditions.append('image_format = ?')
            params.append(image_format)
        
        if extension:
            conditions.append('extension LIKE ?')
            params.append(f'%{extension}%')
        
        if cache_files:
            placeholders = ','.join(['?' for _ in cache_files])
            conditions.append(f'cache_file IN ({placeholders})')
            params.extend(cache_files)
        
        if search:
            conditions.append('(hash LIKE ? OR cache_key LIKE ? OR entry_hash LIKE ? OR extension LIKE ?)')
            search_pattern = f'%{search}%'
            params.extend([search_pattern, search_pattern, search_pattern, search_pattern])
        
        where_clause = 'WHERE ' + ' AND '.join(conditions) if conditions else ''
        
        # Sort order
        sort_mapping = {
            'newest': 'indexed_at DESC',
            'oldest': 'indexed_at ASC',
            'largest': 'data_size DESC',
            'smallest': 'data_size ASC',
            'modified': 'last_modified DESC NULLS LAST',
        }
        order_clause = f'ORDER BY {sort_mapping.get(sort, "indexed_at DESC")}'
        
        # Get total count
        with self._cursor() as cursor:
            cursor.execute(f'SELECT COUNT(*) as count FROM thumbnails {where_clause}', params)
            total = cursor.fetchone()['count']
        
        # Get page data (excluding binary data for list view)
        offset = (page - 1) * per_page
        with self._cursor() as cursor:
            cursor.execute(f'''
                SELECT id, cache_file, cache_key, cache_size, width, height, 
                       data_size, hash, entry_hash, extension, data_checksum,
                       header_checksum, image_format, image_mode, last_modified,
                       flags, indexed_at
                FROM thumbnails 
                {where_clause}
                {order_clause}
                LIMIT ? OFFSET ?
            ''', params + [per_page, offset])
            
            rows = cursor.fetchall()
            thumbnails = []
            for row in rows:
                thumb = dict(row)
                thumb['dimensions'] = f"{thumb['width']}x{thumb['height']}" if thumb['width'] and thumb['height'] else None
                thumbnails.append(thumb)
        
        return thumbnails, total
    
    def get_thumbnails_by_ids(self, ids: List[int]) -> List[Dict[str, Any]]:
        """Get multiple thumbnails by their IDs (including data)."""
        if not ids:
            return []
        
        placeholders = ','.join(['?' for _ in ids])
        with self._cursor() as cursor:
            cursor.execute(f'''
                SELECT id, cache_file, cache_key, cache_size, width, height, 
                       data_size, hash, data, entry_hash, extension, data_checksum,
                       header_checksum, image_format, image_mode, last_modified,
                       flags, indexed_at
                FROM thumbnails 
                WHERE id IN ({placeholders})
            ''', ids)
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        with self._cursor() as cursor:
            # Total count
            cursor.execute('SELECT COUNT(*) as count FROM thumbnails')
            total = cursor.fetchone()['count']
            
            # Count by cache size
            cursor.execute('''
                SELECT cache_size, COUNT(*) as count 
                FROM thumbnails 
                GROUP BY cache_size 
                ORDER BY count DESC
            ''')
            by_size = {row['cache_size']: row['count'] for row in cursor.fetchall()}
            
            # Count by cache file
            cursor.execute('''
                SELECT cache_file, COUNT(*) as count 
                FROM thumbnails 
                GROUP BY cache_file 
                ORDER BY count DESC
            ''')
            by_file = {row['cache_file']: row['count'] for row in cursor.fetchall()}
            
            # Count by image format
            cursor.execute('''
                SELECT image_format, COUNT(*) as count 
                FROM thumbnails 
                WHERE image_format IS NOT NULL
                GROUP BY image_format 
                ORDER BY count DESC
            ''')
            by_format = {row['image_format']: row['count'] for row in cursor.fetchall()}
            
            # Count by extension
            cursor.execute('''
                SELECT extension, COUNT(*) as count 
                FROM thumbnails 
                WHERE extension IS NOT NULL AND extension != ''
                GROUP BY extension 
                ORDER BY count DESC
            ''')
            by_extension = {row['extension']: row['count'] for row in cursor.fetchall()}
            
            # Total data size
            cursor.execute('SELECT SUM(data_size) as total FROM thumbnails')
            total_size = cursor.fetchone()['total'] or 0
        
        last_indexed = self._get_metadata('last_indexed')
        
        return {
            'total_thumbnails': total,
            'by_cache_size': by_size,
            'by_cache_file': by_file,
            'by_image_format': by_format,
            'by_extension': by_extension,
            'total_data_size_bytes': total_size,
            'total_data_size_mb': round(total_size / (1024 * 1024), 2),
            'last_indexed': last_indexed,
            'cache_stats': get_cache_stats()
        }
    
    def get_filter_options(self) -> Dict[str, List[str]]:
        """Get available filter options from the database."""
        options = {
            'cache_sizes': [],
            'image_formats': [],
            'extensions': [],
            'cache_files': [],
        }
        
        with self._cursor() as cursor:
            # Cache sizes
            cursor.execute('SELECT DISTINCT cache_size FROM thumbnails WHERE cache_size IS NOT NULL ORDER BY cache_size')
            options['cache_sizes'] = [row['cache_size'] for row in cursor.fetchall()]
            
            # Image formats
            cursor.execute('SELECT DISTINCT image_format FROM thumbnails WHERE image_format IS NOT NULL ORDER BY image_format')
            options['image_formats'] = [row['image_format'] for row in cursor.fetchall()]
            
            # Extensions
            cursor.execute("SELECT DISTINCT extension FROM thumbnails WHERE extension IS NOT NULL AND extension != '' ORDER BY extension")
            options['extensions'] = [row['extension'] for row in cursor.fetchall()]
            
            # Cache files (indexed)
            cursor.execute('SELECT DISTINCT cache_file FROM thumbnails WHERE cache_file IS NOT NULL ORDER BY cache_file')
            options['cache_files'] = [row['cache_file'] for row in cursor.fetchall()]
        
        return options
    
    def get_indexed_files(self) -> List[str]:
        """Get list of cache files that have been indexed."""
        with self._cursor() as cursor:
            cursor.execute('SELECT DISTINCT cache_file FROM thumbnails ORDER BY cache_file')
            return [row['cache_file'] for row in cursor.fetchall()]
    
    def close(self):
        """Close the database connection."""
        if hasattr(self._local, 'connection') and self._local.connection:
            self._local.connection.close()
            self._local.connection = None


# Global database instance
_db_instance: Optional[ThumbnailDatabase] = None


def get_db() -> ThumbnailDatabase:
    """Get the global database instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = ThumbnailDatabase()
    return _db_instance


# Test function
if __name__ == '__main__':
    print("Thumbnail Database Indexer Test")
    print("=" * 50)
    
    db = get_db()
    
    print("\nIndexing thumbnails...")
    count = db.index_all()
    print(f"Indexed {count} thumbnails")
    
    print("\nDatabase Statistics:")
    stats = db.get_stats()
    print(f"  Total thumbnails: {stats['total_thumbnails']}")
    print(f"  Total data size: {stats['total_data_size_mb']} MB")
    print(f"  Last indexed: {stats['last_indexed']}")
    
    print("\n  By cache size:")
    for size, cnt in stats['by_cache_size'].items():
        print(f"    {size}: {cnt}")
    
    print("\n  By image format:")
    for fmt, cnt in stats['by_image_format'].items():
        print(f"    {fmt}: {cnt}")
    
    print("\n  By extension:")
    for ext, cnt in stats['by_extension'].items():
        print(f"    {ext}: {cnt}")
    
    print("\nFetching first thumbnail with full metadata...")
    thumbs, total = db.get_thumbnails(page=1, per_page=1)
    if thumbs:
        t = thumbs[0]
        print(f"\n  ID: {t['id']}")
        print(f"  Cache File: {t['cache_file']}")
        print(f"  Cache Key: {t['cache_key']}")
        print(f"  Dimensions: {t['dimensions']}")
        print(f"  Data Size: {t['data_size']} bytes")
        print(f"  Hash (MD5): {t['hash']}")
        print(f"  Entry Hash: {t['entry_hash']}")
        print(f"  Extension: {t['extension']}")
        print(f"  Image Format: {t['image_format']}")
        print(f"  Image Mode: {t['image_mode']}")
        print(f"  Data Checksum: {t['data_checksum']}")
        print(f"  Header Checksum: {t['header_checksum']}")
        print(f"  Last Modified: {t['last_modified']}")
        print(f"  Flags: {t['flags']}")
