"""Thumbcache parsing module using dissect.thumbcache library."""

import os
import io
import hashlib
from pathlib import Path
from typing import Iterator, Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from PIL import Image

import config

# Try to import dissect.thumbcache
try:
    from dissect.thumbcache import Thumbcache, ThumbcacheFile
    from dissect.thumbcache.thumbcache_file import ThumbcacheEntry
    from dissect.thumbcache.index import ThumbnailIndex, IndexEntry
    DISSECT_AVAILABLE = True
except ImportError:
    DISSECT_AVAILABLE = False
    ThumbcacheEntry = None
    ThumbnailIndex = None
    IndexEntry = None


@dataclass
class ThumbnailEntry:
    """Represents a parsed thumbnail entry with all available metadata."""
    cache_file: str
    cache_key: str  # identifier
    data: bytes
    data_size: int
    width: Optional[int] = None
    height: Optional[int] = None
    hash: Optional[str] = None  # MD5 hash of data
    cache_size: Optional[str] = None  # e.g., "256", "1024", "sr"
    # Additional metadata
    entry_hash: Optional[str] = None  # Hash from the thumbcache entry itself
    extension: Optional[str] = None  # File extension/type (Vista)
    data_checksum: Optional[str] = None  # Checksum of the data
    header_checksum: Optional[str] = None  # Checksum of the header
    image_format: Optional[str] = None  # Detected image format (JPEG, PNG, BMP, etc.)
    image_mode: Optional[str] = None  # Image color mode (RGB, RGBA, etc.)
    last_modified: Optional[str] = None  # From index file
    flags: Optional[int] = None  # From index file
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'cache_file': self.cache_file,
            'cache_key': self.cache_key,
            'data_size': self.data_size,
            'width': self.width,
            'height': self.height,
            'hash': self.hash,
            'cache_size': self.cache_size,
            'dimensions': f"{self.width}x{self.height}" if self.width and self.height else None,
            'entry_hash': self.entry_hash,
            'extension': self.extension,
            'data_checksum': self.data_checksum,
            'header_checksum': self.header_checksum,
            'image_format': self.image_format,
            'image_mode': self.image_mode,
            'last_modified': self.last_modified,
            'flags': self.flags,
        }


def get_cache_size_from_filename(filename: str) -> Optional[str]:
    """Extract cache size indicator from filename."""
    name = filename.lower()
    if 'thumbcache_32' in name:
        return '32'
    elif 'thumbcache_96' in name:
        return '96'
    elif 'thumbcache_256' in name:
        return '256'
    elif 'thumbcache_1024' in name:
        return '1024'
    elif 'thumbcache_sr' in name:
        return 'sr'
    elif 'thumbcache_wide' in name:
        return 'wide'
    elif 'thumbcache_exif' in name:
        return 'exif'
    elif 'thumbcache_wide_alternate' in name:
        return 'wide_alt'
    elif 'thumbcache_custom' in name:
        return 'custom'
    elif 'thumbcache_16' in name:
        return '16'
    elif 'thumbcache_48' in name:
        return '48'
    elif 'thumbcache_2560' in name:
        return '2560'
    return 'unknown'


def compute_hash(data: bytes) -> str:
    """Compute MD5 hash of thumbnail data."""
    return hashlib.md5(data).hexdigest()


def bytes_to_hex(data: bytes) -> str:
    """Convert bytes to hex string."""
    if data is None:
        return None
    return data.hex()


def get_image_info(data: bytes) -> Dict[str, Any]:
    """Extract detailed image information from thumbnail data."""
    info = {
        'width': None,
        'height': None,
        'format': None,
        'mode': None,
    }
    try:
        with io.BytesIO(data) as buffer:
            img = Image.open(buffer)
            info['width'], info['height'] = img.size
            info['format'] = img.format  # JPEG, PNG, BMP, etc.
            info['mode'] = img.mode  # RGB, RGBA, L, P, etc.
    except Exception:
        pass
    return info


def find_cache_files(cache_path: Optional[Path] = None) -> List[Path]:
    """Find all thumbcache database files in the specified path."""
    if cache_path is None:
        cache_path = config.DEFAULT_CACHE_PATH
    
    if not cache_path.exists():
        return []
    
    cache_files = []
    for filename in config.THUMBCACHE_FILES:
        file_path = cache_path / filename
        if file_path.exists():
            cache_files.append(file_path)
    
    # Also look for any other thumbcache_*.db files not in the predefined list
    for file_path in cache_path.glob('thumbcache_*.db'):
        if file_path not in cache_files and 'idx' not in file_path.name.lower():
            cache_files.append(file_path)
    
    return cache_files


def load_index_data(cache_path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    """
    Load index data from thumbcache_idx.db to get last_modified timestamps.
    
    Returns a dict mapping identifier to index entry data.
    """
    if cache_path is None:
        cache_path = config.DEFAULT_CACHE_PATH
    
    index_path = cache_path / 'thumbcache_idx.db'
    index_data = {}
    
    if not index_path.exists() or not DISSECT_AVAILABLE or ThumbnailIndex is None:
        return index_data
    
    try:
        with open(index_path, 'rb') as f:
            index = ThumbnailIndex(f)
            
            for entry in index.entries():
                try:
                    # Get identifier as string for lookup
                    identifier = entry.identifier
                    if isinstance(identifier, bytes):
                        # Convert bytes identifier to the same format used by cache entries
                        identifier = identifier.hex()
                    else:
                        identifier = str(identifier)
                    
                    # Get last_modified datetime
                    last_modified = None
                    if hasattr(entry, 'last_modified') and entry.last_modified:
                        try:
                            last_modified = entry.last_modified.isoformat()
                        except Exception:
                            pass
                    
                    # Get flags
                    flags = None
                    if hasattr(entry, 'flags'):
                        flags = entry.flags
                    
                    index_data[identifier] = {
                        'last_modified': last_modified,
                        'flags': flags,
                    }
                except Exception:
                    continue
                    
    except Exception as e:
        print(f"Warning: Could not load index data: {e}")
    
    return index_data


def parse_thumbcache_file(file_path: Path, index_data: Optional[Dict] = None) -> Iterator[ThumbnailEntry]:
    """
    Parse a single thumbcache database file.
    
    Yields ThumbnailEntry objects for each valid thumbnail found.
    """
    if not DISSECT_AVAILABLE:
        raise ImportError("dissect.thumbcache is not installed. Run: pip install dissect.thumbcache")
    
    cache_size = get_cache_size_from_filename(file_path.name)
    
    try:
        with open(file_path, 'rb') as f:
            cache_file = ThumbcacheFile(f)
            
            for entry in cache_file.entries():
                # Skip entries without data
                if not hasattr(entry, 'data') or entry.data is None:
                    continue
                
                data = entry.data
                if len(data) == 0:
                    continue
                
                # Get identifier/key
                identifier = getattr(entry, 'identifier', None)
                if identifier is None:
                    identifier = getattr(entry, 'hash', 'unknown')
                cache_key = str(identifier)
                
                # Get entry hash (different from identifier)
                entry_hash = None
                if hasattr(entry, 'hash'):
                    entry_hash = str(entry.hash)
                
                # Get extension (file type - Vista only)
                extension = None
                if hasattr(entry, 'extension'):
                    try:
                        extension = entry.extension
                    except Exception:
                        pass
                
                # Get checksums
                data_checksum = None
                if hasattr(entry, 'data_checksum') and entry.data_checksum:
                    data_checksum = bytes_to_hex(entry.data_checksum)
                
                header_checksum = None
                if hasattr(entry, 'header_checksum') and entry.header_checksum:
                    header_checksum = bytes_to_hex(entry.header_checksum)
                
                # Get image information
                img_info = get_image_info(data)
                
                # Compute MD5 hash of data
                data_hash = compute_hash(data)
                
                # Look up index data for this entry
                last_modified = None
                flags = None
                if index_data:
                    # Try different identifier formats
                    idx_entry = index_data.get(cache_key)
                    if idx_entry is None and identifier:
                        # Try hex format of identifier
                        try:
                            if hasattr(identifier, 'hex'):
                                idx_entry = index_data.get(identifier.hex())
                        except Exception:
                            pass
                    
                    if idx_entry:
                        last_modified = idx_entry.get('last_modified')
                        flags = idx_entry.get('flags')
                
                yield ThumbnailEntry(
                    cache_file=file_path.name,
                    cache_key=cache_key,
                    data=data,
                    data_size=len(data),
                    width=img_info['width'],
                    height=img_info['height'],
                    hash=data_hash,
                    cache_size=cache_size,
                    entry_hash=entry_hash,
                    extension=extension,
                    data_checksum=data_checksum,
                    header_checksum=header_checksum,
                    image_format=img_info['format'],
                    image_mode=img_info['mode'],
                    last_modified=last_modified,
                    flags=flags,
                )
                
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return


def parse_all_thumbcaches(cache_path: Optional[Path] = None, 
                          selected_files: Optional[List[str]] = None) -> Iterator[ThumbnailEntry]:
    """
    Parse all thumbcache files in the specified directory.
    
    Args:
        cache_path: Path to the thumbcache directory
        selected_files: Optional list of cache file names to parse.
                       If None, all files are parsed.
    
    Yields ThumbnailEntry objects for each valid thumbnail found.
    """
    if not DISSECT_AVAILABLE:
        raise ImportError("dissect.thumbcache is not installed. Run: pip install dissect.thumbcache")
    
    if cache_path is None:
        cache_path = config.DEFAULT_CACHE_PATH
    
    # Load index data first for timestamp lookups
    print("Loading index data...")
    index_data = load_index_data(cache_path)
    print(f"Loaded {len(index_data)} index entries")
    
    cache_files = find_cache_files(cache_path)
    
    # Filter to selected files if specified
    if selected_files is not None:
        selected_set = set(selected_files)
        cache_files = [f for f in cache_files if f.name in selected_set]
        print(f"Filtering to {len(cache_files)} selected cache files")
    
    for file_path in cache_files:
        print(f"Parsing {file_path.name}...")
        yield from parse_thumbcache_file(file_path, index_data)


def get_thumbnail_as_png(data: bytes) -> bytes:
    """Convert thumbnail data to PNG format."""
    try:
        with io.BytesIO(data) as input_buffer:
            img = Image.open(input_buffer)
            
            # Convert to RGB if necessary (some images might be in different modes)
            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                # Keep alpha channel
                pass
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            output_buffer = io.BytesIO()
            img.save(output_buffer, format='PNG')
            return output_buffer.getvalue()
    except Exception:
        # Return original data if conversion fails
        return data


def get_cache_stats(cache_path: Optional[Path] = None) -> Dict[str, Any]:
    """Get statistics about the thumbnail cache."""
    if cache_path is None:
        cache_path = config.DEFAULT_CACHE_PATH
    
    cache_files = find_cache_files(cache_path)
    
    stats = {
        'cache_path': str(cache_path),
        'cache_files': [],
        'total_size_bytes': 0,
        'dissect_available': DISSECT_AVAILABLE,
        'index_available': False,
    }
    
    # Check if index file exists
    index_path = cache_path / 'thumbcache_idx.db'
    if index_path.exists():
        stats['index_available'] = True
        try:
            stats['index_size_bytes'] = index_path.stat().st_size
            stats['index_size_mb'] = round(stats['index_size_bytes'] / (1024 * 1024), 2)
        except Exception:
            pass
    
    for file_path in cache_files:
        try:
            size = file_path.stat().st_size
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
            stats['cache_files'].append({
                'name': file_path.name,
                'size_bytes': size,
                'size_mb': round(size / (1024 * 1024), 2),
                'modified': mtime,
            })
            stats['total_size_bytes'] += size
        except Exception:
            pass
    
    stats['total_size_mb'] = round(stats['total_size_bytes'] / (1024 * 1024), 2)
    
    return stats


# Test function
if __name__ == '__main__':
    print("Thumbnail Cache Parser Test")
    print("=" * 50)
    
    # Check if dissect is available
    if not DISSECT_AVAILABLE:
        print("ERROR: dissect.thumbcache is not installed!")
        print("Run: pip install dissect.thumbcache")
        exit(1)
    
    # Get cache stats
    stats = get_cache_stats()
    print(f"\nCache Path: {stats['cache_path']}")
    print(f"Total Size: {stats['total_size_mb']} MB")
    print(f"Index Available: {stats['index_available']}")
    print(f"\nCache Files Found:")
    for cf in stats['cache_files']:
        print(f"  - {cf['name']}: {cf['size_mb']} MB (modified: {cf['modified']})")
    
    # Parse and count thumbnails
    print("\nParsing thumbnails...")
    count = 0
    for entry in parse_all_thumbcaches():
        count += 1
        if count <= 5:
            print(f"\n  [{count}] {entry.cache_file}")
            print(f"      Cache Key: {entry.cache_key}")
            print(f"      Size: {entry.data_size} bytes, Dimensions: {entry.width}x{entry.height}")
            print(f"      Format: {entry.image_format}, Mode: {entry.image_mode}")
            print(f"      Extension: {entry.extension}")
            print(f"      Hash: {entry.hash}")
            print(f"      Entry Hash: {entry.entry_hash}")
            print(f"      Data Checksum: {entry.data_checksum}")
            print(f"      Header Checksum: {entry.header_checksum}")
            print(f"      Last Modified: {entry.last_modified}")
            print(f"      Flags: {entry.flags}")
    
    print(f"\nTotal thumbnails found: {count}")
