"""Export functionality for thumbnails."""

import io
import zipfile
from typing import List, Optional
from datetime import datetime

from parser import get_thumbnail_as_png


def export_single_thumbnail(db, thumb_id: int) -> Optional[bytes]:
    """
    Export a single thumbnail as PNG.
    
    Args:
        db: ThumbnailDatabase instance
        thumb_id: Thumbnail ID to export
        
    Returns:
        PNG data as bytes, or None if not found
    """
    data = db.get_thumbnail_data(thumb_id)
    if data is None:
        return None
    
    return get_thumbnail_as_png(data)


def export_thumbnails_to_zip(db, ids: List[int]) -> bytes:
    """
    Export multiple thumbnails as a ZIP archive.
    
    Args:
        db: ThumbnailDatabase instance
        ids: List of thumbnail IDs to export
        
    Returns:
        ZIP file data as bytes
    """
    # Fetch all thumbnails
    thumbnails = db.get_thumbnails_by_ids(ids)
    
    # Create ZIP in memory
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for thumb in thumbnails:
            # Generate filename
            cache_size = thumb.get('cache_size', 'unknown')
            hash_prefix = thumb.get('hash', 'unknown')[:8] if thumb.get('hash') else 'unknown'
            ext = thumb.get('extension', '').replace('.', '') if thumb.get('extension') else ''
            
            # Create organized folder structure
            folder = f"{cache_size}"
            filename = f"{thumb['id']}_{hash_prefix}"
            if ext:
                filename += f"_{ext}"
            filename += ".png"
            
            full_path = f"{folder}/{filename}"
            
            # Convert to PNG
            png_data = get_thumbnail_as_png(thumb['data'])
            
            # Add to ZIP
            zip_file.writestr(full_path, png_data)
        
        # Add metadata file with all available information
        metadata = generate_export_metadata(thumbnails)
        zip_file.writestr('metadata.txt', metadata)
        
        # Also create a CSV file for easier analysis
        csv_data = generate_export_csv(thumbnails)
        zip_file.writestr('metadata.csv', csv_data)
    
    zip_buffer.seek(0)
    return zip_buffer.getvalue()


def generate_export_metadata(thumbnails: List[dict]) -> str:
    """Generate a detailed metadata text file for the export."""
    lines = [
        "=" * 70,
        "THUMBNAIL CACHE EXPORT",
        "=" * 70,
        f"Exported: {datetime.now().isoformat()}",
        f"Total thumbnails: {len(thumbnails)}",
        "",
        "NOTE: Original file paths are not stored in the thumbnail cache.",
        "      They can be recovered from Windows Search (Windows.edb) database.",
        "",
        "=" * 70,
        ""
    ]
    
    for idx, thumb in enumerate(thumbnails, 1):
        lines.extend([
            f"[{idx}] Thumbnail ID: {thumb['id']}",
            "-" * 50,
            "",
            "  IMAGE INFORMATION:",
            f"    Dimensions:      {thumb.get('width', '?')}x{thumb.get('height', '?')}",
            f"    Data Size:       {thumb.get('data_size', 0):,} bytes",
            f"    Image Format:    {thumb.get('image_format', 'Unknown')}",
            f"    Color Mode:      {thumb.get('image_mode', 'Unknown')}",
            f"    File Extension:  {thumb.get('extension', 'Unknown')}",
            "",
            "  CACHE INFORMATION:",
            f"    Cache File:      {thumb.get('cache_file', 'Unknown')}",
            f"    Cache Size Type: {thumb.get('cache_size', 'Unknown')}",
            f"    Cache Key (ID):  {thumb.get('cache_key', 'Unknown')}",
            f"    Entry Hash:      {thumb.get('entry_hash', 'Unknown')}",
            "",
            "  CHECKSUMS & HASHES:",
            f"    MD5 Hash:        {thumb.get('hash', 'Unknown')}",
            f"    Data Checksum:   {thumb.get('data_checksum', 'Unknown')}",
            f"    Header Checksum: {thumb.get('header_checksum', 'Unknown')}",
            "",
            "  TIMESTAMPS & FLAGS:",
            f"    Last Modified:   {thumb.get('last_modified', 'Unknown')}",
            f"    Indexed At:      {thumb.get('indexed_at', 'Unknown')}",
            f"    Flags:           {format_flags(thumb.get('flags'))}",
            "",
        ])
    
    return '\n'.join(lines)


def generate_export_csv(thumbnails: List[dict]) -> str:
    """Generate a CSV file with all metadata for easier analysis."""
    # CSV header
    headers = [
        'id', 'cache_file', 'cache_key', 'cache_size', 'width', 'height',
        'data_size', 'image_format', 'image_mode', 'extension', 'hash',
        'entry_hash', 'data_checksum', 'header_checksum', 'last_modified',
        'indexed_at', 'flags'
    ]
    
    lines = [','.join(headers)]
    
    for thumb in thumbnails:
        row = [
            str(thumb.get('id', '')),
            escape_csv(thumb.get('cache_file', '')),
            escape_csv(thumb.get('cache_key', '')),
            escape_csv(thumb.get('cache_size', '')),
            str(thumb.get('width', '')),
            str(thumb.get('height', '')),
            str(thumb.get('data_size', '')),
            escape_csv(thumb.get('image_format', '')),
            escape_csv(thumb.get('image_mode', '')),
            escape_csv(thumb.get('extension', '')),
            escape_csv(thumb.get('hash', '')),
            escape_csv(thumb.get('entry_hash', '')),
            escape_csv(thumb.get('data_checksum', '')),
            escape_csv(thumb.get('header_checksum', '')),
            escape_csv(thumb.get('last_modified', '')),
            escape_csv(thumb.get('indexed_at', '')),
            str(thumb.get('flags', ''))
        ]
        lines.append(','.join(row))
    
    return '\n'.join(lines)


def escape_csv(value) -> str:
    """Escape a value for CSV format."""
    if value is None:
        return ''
    value = str(value)
    if ',' in value or '"' in value or '\n' in value:
        value = '"' + value.replace('"', '""') + '"'
    return value


def format_flags(flags) -> str:
    """Format flags value for display."""
    if flags is None:
        return 'Unknown'
    return f"0x{flags:08X} ({flags})"


def get_export_filename(thumb: dict, format: str = 'png') -> str:
    """
    Generate a descriptive filename for a thumbnail export.
    
    Args:
        thumb: Thumbnail dictionary
        format: Output format extension
        
    Returns:
        Filename string
    """
    cache_size = thumb.get('cache_size', 'unknown')
    thumb_id = thumb.get('id', 0)
    hash_prefix = thumb.get('hash', 'unknown')[:8] if thumb.get('hash') else 'unknown'
    
    return f"thumb_{cache_size}_{thumb_id}_{hash_prefix}.{format}"
