/**
 * Thumbnail Master - Frontend JavaScript
 * Modern UI with smooth animations
 */

class ThumbnailViewer {
    constructor() {
        this.currentPage = 1;
        this.perPage = parseInt(localStorage.getItem('thumbnailsPerPage')) || 50;
        this.totalThumbnails = 0;
        this.selectedIds = new Set();
        this.selectMode = false;
        this.currentFilters = {
            search: '',
            size: '',
            format: '',
            sort: 'newest'
        };
        
        // Cache file selection state
        this.availableCacheFiles = [];
        this.selectedCacheFiles = new Set();
        this.indexedCacheFiles = new Set();
        
        // Animation state
        this.isLoading = false;
        
        // Performance mode threshold - disable animations above this count
        this.performanceThreshold = 100;
        
        // Virtual scrolling settings
        this.virtualScrollThreshold = 200; // Enable virtual scroll above this count
        this.virtualScrollEnabled = false;
        this.allThumbnails = []; // Store all thumbnails for virtual scroll
        this.visibleRange = { start: 0, end: 0 };
        this.rowHeight = 172; // thumb size (160) + gap (12)
        this.itemsPerRow = 1;
        this.scrollRAF = null;
        
        this.init();
    }
    
    init() {
        this.bindElements();
        this.bindEvents();
        this.bindScrollOptimizations();
        this.loadCacheFiles();
        this.loadFilterOptions();
        this.loadThumbnails();
        this.loadStats();
    }
    
    bindScrollOptimizations() {
        // Disable hover effects during scroll for better performance
        let scrollTimeout;
        let isScrolling = false;
        
        window.addEventListener('scroll', () => {
            if (!isScrolling) {
                isScrolling = true;
                document.body.classList.add('is-scrolling');
            }
            
            clearTimeout(scrollTimeout);
            scrollTimeout = setTimeout(() => {
                isScrolling = false;
                document.body.classList.remove('is-scrolling');
            }, 150);
        }, { passive: true });
    }
    
    bindElements() {
        this.gallery = document.getElementById('thumbnail-gallery');
        this.loadingIndicator = document.getElementById('loading-indicator');
        this.emptyState = document.getElementById('empty-state');
        this.paginationNav = document.getElementById('pagination-nav');
        this.paginationNavTop = document.getElementById('pagination-nav-top');
        this.statsBadge = document.getElementById('stats-badge');
        this.searchInput = document.getElementById('search-input');
        this.sizeFilter = document.getElementById('size-filter');
        this.formatFilter = document.getElementById('format-filter');
        this.sortFilter = document.getElementById('sort-filter');
        this.perPageFilter = document.getElementById('per-page-filter');
        this.selectModeBtn = document.getElementById('select-mode-btn');
        this.exportBtn = document.getElementById('export-btn');
        this.refreshBtn = document.getElementById('refresh-btn');
        this.selectedCount = document.getElementById('selected-count');
        this.modal = new bootstrap.Modal(document.getElementById('thumbnail-modal'));
        this.toast = new bootstrap.Toast(document.getElementById('notification-toast'));
        
        // Cache file selection elements
        this.cacheFilesContainer = document.getElementById('cache-files-container');
        this.selectedFilesCount = document.getElementById('selected-files-count');
        this.selectAllFilesBtn = document.getElementById('select-all-files-btn');
        this.deselectAllFilesBtn = document.getElementById('deselect-all-files-btn');
        
        // Set initial per-page value
        this.perPageFilter.value = this.perPage;
    }
    
    bindEvents() {
        // Search with debounce
        let searchTimeout;
        this.searchInput.addEventListener('input', () => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                this.currentFilters.search = this.searchInput.value;
                this.currentPage = 1;
                this.loadThumbnails();
            }, 300);
        });
        
        // Filters
        this.sizeFilter.addEventListener('change', () => {
            this.currentFilters.size = this.sizeFilter.value;
            this.currentPage = 1;
            this.loadThumbnails();
        });
        
        this.formatFilter.addEventListener('change', () => {
            this.currentFilters.format = this.formatFilter.value;
            this.currentPage = 1;
            this.loadThumbnails();
        });
        
        this.sortFilter.addEventListener('change', () => {
            this.currentFilters.sort = this.sortFilter.value;
            this.currentPage = 1;
            this.loadThumbnails();
        });
        
        // Per-page filter
        this.perPageFilter.addEventListener('change', () => {
            this.perPage = parseInt(this.perPageFilter.value);
            localStorage.setItem('thumbnailsPerPage', this.perPage);
            this.currentPage = 1;
            this.loadThumbnails();
        });
        
        // Select Mode
        this.selectModeBtn.addEventListener('click', () => this.toggleSelectMode());
        
        // Export
        this.exportBtn.addEventListener('click', () => this.exportSelected());
        
        // Refresh
        this.refreshBtn.addEventListener('click', () => this.refreshIndex());
        
        // Modal export button
        document.getElementById('modal-export-btn').addEventListener('click', () => {
            const id = document.getElementById('modal-export-btn').dataset.thumbId;
            if (id) this.exportSingle(id);
        });
        
        // Cache file selection buttons
        this.selectAllFilesBtn.addEventListener('click', () => this.selectAllCacheFiles());
        this.deselectAllFilesBtn.addEventListener('click', () => this.deselectAllCacheFiles());
        
        // Event delegation for thumbnail gallery (instead of per-card listeners)
        // This is MUCH more performant for large numbers of items
        this.gallery.addEventListener('click', (e) => {
            const card = e.target.closest('.thumbnail-card');
            if (!card) return;
            
            if (this.selectMode) {
                e.preventDefault();
                const id = parseInt(card.dataset.id);
                this.toggleSelection(id, card);
            } else {
                try {
                    const thumbData = JSON.parse(card.dataset.thumbData);
                    this.showThumbnailDetail(thumbData);
                } catch (err) {
                    console.error('Failed to parse thumbnail data:', err);
                }
            }
        });
        
        // Keyboard accessibility via delegation
        this.gallery.addEventListener('keydown', (e) => {
            if (e.key !== 'Enter' && e.key !== ' ') return;
            
            const card = e.target.closest('.thumbnail-card');
            if (!card) return;
            
            e.preventDefault();
            const id = parseInt(card.dataset.id);
            
            if (this.selectMode) {
                this.toggleSelection(id, card);
            } else {
                try {
                    const thumbData = JSON.parse(card.dataset.thumbData);
                    this.showThumbnailDetail(thumbData);
                } catch (err) {
                    console.error('Failed to parse thumbnail data:', err);
                }
            }
        });
    }
    
    async loadFilterOptions() {
        try {
            const response = await fetch('/api/filters');
            const data = await response.json();
            
            // Populate format filter
            if (data.image_formats && data.image_formats.length > 0) {
                data.image_formats.forEach(fmt => {
                    const option = document.createElement('option');
                    option.value = fmt;
                    option.textContent = fmt;
                    this.formatFilter.appendChild(option);
                });
            }
        } catch (error) {
            console.error('Failed to load filter options:', error);
        }
    }
    
    async loadCacheFiles() {
        try {
            const response = await fetch('/api/cache-files');
            const data = await response.json();
            
            this.availableCacheFiles = data.available || [];
            this.indexedCacheFiles = new Set(data.indexed || []);
            
            // Load saved selection from localStorage, or select all indexed files by default
            const savedSelection = localStorage.getItem('selectedCacheFiles');
            if (savedSelection) {
                try {
                    const parsed = JSON.parse(savedSelection);
                    this.selectedCacheFiles = new Set(parsed.filter(f => 
                        this.availableCacheFiles.some(af => af.name === f)
                    ));
                } catch {
                    this.selectedCacheFiles = new Set(this.indexedCacheFiles);
                }
            } else {
                // Default: select all indexed files
                this.selectedCacheFiles = new Set(this.indexedCacheFiles);
            }
            
            this.renderCacheFiles();
        } catch (error) {
            console.error('Failed to load cache files:', error);
            this.cacheFilesContainer.innerHTML = '<span class="text-danger small">Failed to load database files</span>';
        }
    }
    
    renderCacheFiles() {
        this.cacheFilesContainer.innerHTML = '';
        
        if (this.availableCacheFiles.length === 0) {
            this.cacheFilesContainer.innerHTML = '<span class="text-muted small">No database files found</span>';
            this.updateSelectedFilesCount();
            return;
        }
        
        this.availableCacheFiles.forEach(file => {
            const isSelected = this.selectedCacheFiles.has(file.name);
            const isIndexed = this.indexedCacheFiles.has(file.name);
            
            const badge = document.createElement('div');
            badge.className = `cache-file-badge ${isSelected ? 'selected' : ''} ${isIndexed ? 'indexed' : 'not-indexed'}`;
            badge.dataset.filename = file.name;
            badge.title = `${file.name}\nSize: ${file.size_mb} MB\nModified: ${this.formatTimestamp(file.modified)}${isIndexed ? '\n(Indexed)' : '\n(Not indexed)'}`;
            
            badge.innerHTML = `
                <input type="checkbox" class="cache-file-checkbox" ${isSelected ? 'checked' : ''}>
                <span class="cache-file-name">${file.cache_size || file.name}</span>
                <span class="cache-file-size">${file.size_mb}MB</span>
                ${!isIndexed ? '<i class="bi bi-exclamation-circle text-warning" title="Not indexed"></i>' : ''}
            `;
            
            badge.addEventListener('click', (e) => {
                if (e.target.type !== 'checkbox') {
                    this.toggleCacheFile(file.name);
                }
            });
            
            const checkbox = badge.querySelector('.cache-file-checkbox');
            checkbox.addEventListener('change', () => {
                this.toggleCacheFile(file.name);
            });
            
            this.cacheFilesContainer.appendChild(badge);
        });
        
        this.updateSelectedFilesCount();
    }
    
    toggleCacheFile(filename) {
        if (this.selectedCacheFiles.has(filename)) {
            this.selectedCacheFiles.delete(filename);
        } else {
            this.selectedCacheFiles.add(filename);
        }
        
        // Update UI
        const badge = this.cacheFilesContainer.querySelector(`[data-filename="${filename}"]`);
        if (badge) {
            badge.classList.toggle('selected', this.selectedCacheFiles.has(filename));
            badge.querySelector('.cache-file-checkbox').checked = this.selectedCacheFiles.has(filename);
        }
        
        this.updateSelectedFilesCount();
        this.saveCacheFileSelection();
        
        // Reload thumbnails with new filter
        this.currentPage = 1;
        this.loadThumbnails();
    }
    
    selectAllCacheFiles() {
        this.selectedCacheFiles = new Set(this.availableCacheFiles.map(f => f.name));
        this.renderCacheFiles();
        this.saveCacheFileSelection();
        this.currentPage = 1;
        this.loadThumbnails();
    }
    
    deselectAllCacheFiles() {
        this.selectedCacheFiles.clear();
        this.renderCacheFiles();
        this.saveCacheFileSelection();
        this.currentPage = 1;
        this.loadThumbnails();
    }
    
    updateSelectedFilesCount() {
        const count = this.selectedCacheFiles.size;
        const total = this.availableCacheFiles.length;
        this.selectedFilesCount.textContent = `${count} of ${total} selected`;
    }
    
    saveCacheFileSelection() {
        localStorage.setItem('selectedCacheFiles', JSON.stringify(Array.from(this.selectedCacheFiles)));
    }
    
    getSelectedCacheFilesParam() {
        // Only filter if not all files are selected
        if (this.selectedCacheFiles.size === 0) {
            return null;  // No files selected - will show nothing (special case)
        }
        if (this.selectedCacheFiles.size === this.availableCacheFiles.length) {
            return '';  // All files selected - no filter needed
        }
        return Array.from(this.selectedCacheFiles).join(',');
    }
    
    async loadThumbnails() {
        this.showLoading(true);
        
        try {
            // Check if no cache files are selected
            const cacheFilesParam = this.getSelectedCacheFilesParam();
            if (cacheFilesParam === null) {
                // No files selected - show empty results with message
                this.totalThumbnails = 0;
                this.renderThumbnails([], true);  // Pass flag for "no databases selected"
                this.renderPagination(0);
                this.showLoading(false);
                return;
            }
            
            const params = new URLSearchParams({
                page: this.currentPage,
                per_page: this.perPage,
                search: this.currentFilters.search,
                size: this.currentFilters.size,
                format: this.currentFilters.format,
                sort: this.currentFilters.sort
            });
            
            // Add cache files filter if not all files are selected
            if (cacheFilesParam) {
                params.set('cache_files', cacheFilesParam);
            }
            
            const response = await fetch(`/api/thumbnails?${params}`);
            const data = await response.json();
            
            this.totalThumbnails = data.total;
            this.renderThumbnails(data.thumbnails);
            this.renderPagination(data.total);
            
        } catch (error) {
            console.error('Failed to load thumbnails:', error);
            this.showNotification('Error', 'Failed to load thumbnails', 'danger');
        }
        
        this.showLoading(false);
    }
    
    renderThumbnails(thumbnails, noDatabasesSelected = false) {
        // Clean up any existing virtual scroll
        this.disableVirtualScroll();
        
        if (thumbnails.length === 0) {
            this.gallery.classList.add('d-none');
            this.emptyState.classList.remove('d-none');
            this.paginationNav.classList.add('d-none');
            this.paginationNavTop.classList.add('d-none');
            
            // Update empty state message based on why there are no results
            const emptyTitle = this.emptyState.querySelector('h4');
            const emptyText = this.emptyState.querySelector('p');
            if (noDatabasesSelected) {
                emptyTitle.textContent = 'No Databases Selected';
                emptyText.textContent = 'Select one or more database files above to view thumbnails.';
            } else {
                emptyTitle.textContent = 'No Thumbnails Found';
                emptyText.textContent = 'Click "Refresh" to scan your thumbnail cache.';
            }
            return;
        }
        
        this.emptyState.classList.add('d-none');
        this.gallery.classList.remove('d-none');
        
        // Enable/disable performance mode based on item count
        const isPerformanceMode = thumbnails.length > this.performanceThreshold;
        document.body.classList.toggle('performance-mode', isPerformanceMode);
        
        // Use virtual scrolling for very large datasets
        if (thumbnails.length > this.virtualScrollThreshold) {
            this.enableVirtualScroll(thumbnails);
            return;
        }
        
        // Standard rendering for smaller datasets
        const fragment = document.createDocumentFragment();
        const showAnimations = !isPerformanceMode;
        
        thumbnails.forEach((thumb, index) => {
            const card = this.createThumbnailCard(thumb, index, showAnimations);
            fragment.appendChild(card);
        });
        
        this.gallery.innerHTML = '';
        this.gallery.appendChild(fragment);
    }
    
    enableVirtualScroll(thumbnails) {
        this.virtualScrollEnabled = true;
        this.allThumbnails = thumbnails;
        
        // Calculate items per row based on container width
        this.calculateItemsPerRow();
        
        // Calculate total height needed
        const totalRows = Math.ceil(thumbnails.length / this.itemsPerRow);
        const totalHeight = totalRows * this.rowHeight;
        
        // Set up the gallery for virtual scrolling
        this.gallery.innerHTML = '';
        this.gallery.style.position = 'relative';
        this.gallery.style.height = `${totalHeight}px`;
        this.gallery.classList.add('virtual-scroll');
        
        // Create a container for visible items
        this.virtualContainer = document.createElement('div');
        this.virtualContainer.className = 'virtual-scroll-container';
        this.virtualContainer.style.position = 'absolute';
        this.virtualContainer.style.top = '0';
        this.virtualContainer.style.left = '0';
        this.virtualContainer.style.right = '0';
        this.gallery.appendChild(this.virtualContainer);
        
        // Bind scroll handler with passive flag for performance
        this.boundScrollHandler = this.onVirtualScroll.bind(this);
        this.boundResizeHandler = this.onVirtualResize.bind(this);
        window.addEventListener('scroll', this.boundScrollHandler, { passive: true });
        window.addEventListener('resize', this.boundResizeHandler, { passive: true });
        
        // Initial render
        this.updateVirtualScroll();
    }
    
    onVirtualResize() {
        // Debounce resize events
        if (this.resizeTimeout) clearTimeout(this.resizeTimeout);
        
        this.resizeTimeout = setTimeout(() => {
            if (!this.virtualScrollEnabled) return;
            
            // Recalculate layout
            const oldItemsPerRow = this.itemsPerRow;
            this.calculateItemsPerRow();
            
            // Only recalculate if items per row changed
            if (oldItemsPerRow !== this.itemsPerRow) {
                const totalRows = Math.ceil(this.allThumbnails.length / this.itemsPerRow);
                const totalHeight = totalRows * this.rowHeight;
                this.gallery.style.height = `${totalHeight}px`;
                this.visibleRange = { start: -1, end: -1 }; // Force re-render
            }
            
            this.updateVirtualScroll();
        }, 100);
    }
    
    disableVirtualScroll() {
        if (this.virtualScrollEnabled) {
            this.virtualScrollEnabled = false;
            this.allThumbnails = [];
            
            if (this.boundScrollHandler) {
                window.removeEventListener('scroll', this.boundScrollHandler);
                this.boundScrollHandler = null;
            }
            
            if (this.boundResizeHandler) {
                window.removeEventListener('resize', this.boundResizeHandler);
                this.boundResizeHandler = null;
            }
            
            if (this.scrollRAF) {
                cancelAnimationFrame(this.scrollRAF);
                this.scrollRAF = null;
            }
            
            if (this.resizeTimeout) {
                clearTimeout(this.resizeTimeout);
                this.resizeTimeout = null;
            }
            
            this.gallery.style.height = '';
            this.gallery.style.position = '';
            this.gallery.classList.remove('virtual-scroll');
            this.visibleRange = { start: 0, end: 0 };
        }
    }
    
    calculateItemsPerRow() {
        const galleryWidth = this.gallery.offsetWidth;
        const itemWidth = 172; // thumb size (160) + gap (12)
        this.itemsPerRow = Math.max(1, Math.floor(galleryWidth / itemWidth));
    }
    
    onVirtualScroll() {
        // Use requestAnimationFrame to throttle scroll updates
        if (this.scrollRAF) return;
        
        this.scrollRAF = requestAnimationFrame(() => {
            this.scrollRAF = null;
            this.updateVirtualScroll();
        });
    }
    
    updateVirtualScroll() {
        if (!this.virtualScrollEnabled) return;
        
        // Recalculate items per row (in case of resize)
        this.calculateItemsPerRow();
        
        const scrollTop = window.scrollY;
        const viewportHeight = window.innerHeight;
        const galleryRect = this.gallery.getBoundingClientRect();
        const galleryTop = galleryRect.top + scrollTop;
        
        // Calculate visible range with buffer (render 2 extra rows above/below)
        const buffer = 3;
        const relativeScroll = Math.max(0, scrollTop - galleryTop);
        const startRow = Math.max(0, Math.floor(relativeScroll / this.rowHeight) - buffer);
        const visibleRows = Math.ceil(viewportHeight / this.rowHeight) + (buffer * 2);
        const endRow = startRow + visibleRows;
        
        const startIndex = startRow * this.itemsPerRow;
        const endIndex = Math.min(this.allThumbnails.length, (endRow + 1) * this.itemsPerRow);
        
        // Only re-render if the range changed
        if (startIndex === this.visibleRange.start && endIndex === this.visibleRange.end) {
            return;
        }
        
        this.visibleRange = { start: startIndex, end: endIndex };
        
        // Render only visible items
        const fragment = document.createDocumentFragment();
        
        for (let i = startIndex; i < endIndex; i++) {
            const thumb = this.allThumbnails[i];
            if (!thumb) continue;
            
            const card = this.createThumbnailCard(thumb, i, false);
            
            // Position the card absolutely
            const row = Math.floor(i / this.itemsPerRow);
            const col = i % this.itemsPerRow;
            card.style.position = 'absolute';
            card.style.top = `${row * this.rowHeight}px`;
            card.style.left = `${col * 172}px`;
            
            fragment.appendChild(card);
        }
        
        this.virtualContainer.innerHTML = '';
        this.virtualContainer.appendChild(fragment);
    }
    
    createThumbnailCard(thumb, index = 0, showAnimations = true) {
        const col = document.createElement('div');
        col.className = 'col-auto';
        
        // Only set animation delay for small result sets
        if (showAnimations && index < 20) {
            col.style.animationDelay = `${index * 0.02}s`;
        }
        
        const card = document.createElement('div');
        card.className = 'thumbnail-card';
        card.dataset.id = thumb.id;
        
        // Store thumb data for event delegation
        card.dataset.thumbData = JSON.stringify({
            id: thumb.id,
            dimensions: thumb.dimensions,
            data_size: thumb.data_size,
            image_format: thumb.image_format,
            image_mode: thumb.image_mode,
            extension: thumb.extension,
            cache_file: thumb.cache_file,
            cache_size: thumb.cache_size,
            cache_key: thumb.cache_key,
            entry_hash: thumb.entry_hash,
            hash: thumb.hash,
            data_checksum: thumb.data_checksum,
            header_checksum: thumb.header_checksum,
            last_modified: thumb.last_modified,
            indexed_at: thumb.indexed_at,
            flags: thumb.flags
        });
        
        if (this.selectedIds.has(thumb.id)) {
            card.classList.add('selected');
        }
        
        // Build badge text - don't show "unknown" cache size
        let badgeText = '';
        if (thumb.cache_size && thumb.cache_size !== 'unknown') {
            badgeText = thumb.cache_size;
        }
        if (thumb.image_format) {
            badgeText += (badgeText ? ' ' : '') + thumb.image_format;
        }
        if (!badgeText) {
            badgeText = '?';
        }
        
        card.innerHTML = `
            <input type="checkbox" class="select-checkbox" ${this.selectedIds.has(thumb.id) ? 'checked' : ''}>
            <img src="/api/thumbnail/${thumb.id}" alt="Thumbnail" loading="lazy" decoding="async">
            <span class="size-badge">${badgeText}</span>
        `;
        
        // Add keyboard accessibility (no event listener - handled by delegation)
        card.setAttribute('tabindex', '0');
        card.setAttribute('role', 'button');
        
        col.appendChild(card);
        return col;
    }
    
    toggleSelectMode() {
        this.selectMode = !this.selectMode;
        document.body.classList.toggle('select-mode', this.selectMode);
        
        if (this.selectMode) {
            this.selectModeBtn.classList.add('active');
            this.selectModeBtn.innerHTML = '<i class="bi bi-x-lg"></i><span class="d-none d-lg-inline ms-1">Cancel</span>';
            this.exportBtn.classList.remove('d-none');
        } else {
            this.selectModeBtn.classList.remove('active');
            this.selectModeBtn.innerHTML = '<i class="bi bi-check2-square"></i><span class="d-none d-lg-inline ms-1">Select</span>';
            this.exportBtn.classList.add('d-none');
            this.selectedIds.clear();
            this.updateSelectedCount();
            document.querySelectorAll('.thumbnail-card.selected').forEach(el => {
                el.classList.remove('selected');
                el.querySelector('.select-checkbox').checked = false;
            });
        }
    }
    
    toggleSelection(id, card) {
        if (this.selectedIds.has(id)) {
            this.selectedIds.delete(id);
            card.classList.remove('selected');
            card.querySelector('.select-checkbox').checked = false;
        } else {
            this.selectedIds.add(id);
            card.classList.add('selected');
            card.querySelector('.select-checkbox').checked = true;
        }
        this.updateSelectedCount();
    }
    
    updateSelectedCount() {
        this.selectedCount.textContent = this.selectedIds.size;
    }
    
    showThumbnailDetail(thumb) {
        // Set image
        document.getElementById('modal-image').src = `/api/thumbnail/${thumb.id}`;
        
        // Image Information
        document.getElementById('meta-dimensions').textContent = thumb.dimensions || '-';
        document.getElementById('meta-size').textContent = thumb.data_size ? this.formatBytes(thumb.data_size) : '-';
        document.getElementById('meta-image-format').textContent = thumb.image_format || '-';
        document.getElementById('meta-image-mode').textContent = thumb.image_mode || '-';
        document.getElementById('meta-extension').textContent = thumb.extension || '-';
        
        // Cache Information
        document.getElementById('meta-cache-file').textContent = thumb.cache_file || '-';
        document.getElementById('meta-cache-size').textContent = this.formatCacheSize(thumb.cache_size);
        document.getElementById('meta-cache-key').textContent = thumb.cache_key || '-';
        document.getElementById('meta-entry-hash').textContent = thumb.entry_hash || '-';
        
        // Checksums & Hashes
        document.getElementById('meta-hash').textContent = thumb.hash || '-';
        document.getElementById('meta-data-checksum').textContent = thumb.data_checksum || '-';
        document.getElementById('meta-header-checksum').textContent = thumb.header_checksum || '-';
        
        // Timestamps & Flags
        document.getElementById('meta-last-modified').textContent = this.formatTimestamp(thumb.last_modified);
        document.getElementById('meta-indexed-at').textContent = this.formatTimestamp(thumb.indexed_at);
        document.getElementById('meta-flags').textContent = thumb.flags !== null ? `0x${thumb.flags.toString(16).toUpperCase()}` : '-';
        
        // Set export button data
        document.getElementById('modal-export-btn').dataset.thumbId = thumb.id;
        
        this.modal.show();
    }
    
    formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    formatCacheSize(size) {
        const sizeMap = {
            '16': '16x16 (Tiny)',
            '32': '32x32 (Small)',
            '48': '48x48 (Medium Small)',
            '96': '96x96 (Medium)',
            '256': '256x256 (Large)',
            '1024': '1024px (Extra Large)',
            '2560': '2560px (Huge)',
            'sr': 'Super Resolution',
            'wide': 'Wide Format',
            'wide_alt': 'Wide Alternate',
            'exif': 'EXIF Based',
            'custom': 'Custom Size'
        };
        return sizeMap[size] || size || '-';
    }
    
    formatTimestamp(timestamp) {
        if (!timestamp) return '-';
        try {
            const date = new Date(timestamp);
            return date.toLocaleString();
        } catch {
            return timestamp;
        }
    }
    
    renderPagination(total) {
        const totalPages = Math.ceil(total / this.perPage);
        
        if (totalPages <= 1) {
            this.paginationNav.classList.add('d-none');
            this.paginationNavTop.classList.add('d-none');
            return;
        }
        
        this.paginationNav.classList.remove('d-none');
        this.paginationNavTop.classList.remove('d-none');
        
        // Render pagination for both top and bottom
        this.renderPaginationControls(this.paginationNav.querySelector('ul'), totalPages);
        this.renderPaginationControls(this.paginationNavTop.querySelector('ul'), totalPages);
    }
    
    renderPaginationControls(ul, totalPages) {
        ul.innerHTML = '';
        
        // Jump to beginning button
        const firstLi = document.createElement('li');
        firstLi.className = `page-item ${this.currentPage === 1 ? 'disabled' : ''}`;
        firstLi.innerHTML = '<a class="page-link" href="#" title="Jump to beginning"><i class="bi bi-chevron-bar-left"></i></a>';
        firstLi.addEventListener('click', (e) => {
            e.preventDefault();
            if (this.currentPage > 1) {
                this.currentPage = 1;
                this.loadThumbnails();
                window.scrollTo({ top: 0, behavior: 'smooth' });
            }
        });
        ul.appendChild(firstLi);
        
        // Previous button
        const prevLi = document.createElement('li');
        prevLi.className = `page-item ${this.currentPage === 1 ? 'disabled' : ''}`;
        prevLi.innerHTML = '<a class="page-link" href="#" title="Previous page">&laquo;</a>';
        prevLi.addEventListener('click', (e) => {
            e.preventDefault();
            if (this.currentPage > 1) {
                this.currentPage--;
                this.loadThumbnails();
                window.scrollTo({ top: 0, behavior: 'smooth' });
            }
        });
        ul.appendChild(prevLi);
        
        // Page numbers with smart display
        this.renderPageNumbers(ul, totalPages);
        
        // Next button
        const nextLi = document.createElement('li');
        nextLi.className = `page-item ${this.currentPage === totalPages ? 'disabled' : ''}`;
        nextLi.innerHTML = '<a class="page-link" href="#" title="Next page">&raquo;</a>';
        nextLi.addEventListener('click', (e) => {
            e.preventDefault();
            if (this.currentPage < totalPages) {
                this.currentPage++;
                this.loadThumbnails();
                window.scrollTo({ top: 0, behavior: 'smooth' });
            }
        });
        ul.appendChild(nextLi);
        
        // Jump to end button
        const lastLi = document.createElement('li');
        lastLi.className = `page-item ${this.currentPage === totalPages ? 'disabled' : ''}`;
        lastLi.innerHTML = '<a class="page-link" href="#" title="Jump to end"><i class="bi bi-chevron-bar-right"></i></a>';
        lastLi.addEventListener('click', (e) => {
            e.preventDefault();
            if (this.currentPage < totalPages) {
                this.currentPage = totalPages;
                this.loadThumbnails();
                window.scrollTo({ top: 0, behavior: 'smooth' });
            }
        });
        ul.appendChild(lastLi);
        
        // Page input (direct page navigation)
        const inputLi = document.createElement('li');
        inputLi.className = 'page-item page-input-item';
        inputLi.innerHTML = `
            <div class="page-input-container">
                <span class="page-input-label">Page</span>
                <input type="number" class="form-control page-number-input" 
                       min="1" max="${totalPages}" value="${this.currentPage}"
                       title="Enter page number">
                <span class="page-input-label">of ${totalPages}</span>
            </div>
        `;
        
        const input = inputLi.querySelector('.page-number-input');
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                const pageNum = parseInt(input.value);
                if (pageNum >= 1 && pageNum <= totalPages) {
                    this.currentPage = pageNum;
                    this.loadThumbnails();
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                } else {
                    input.value = this.currentPage;
                }
            }
        });
        
        input.addEventListener('blur', () => {
            const pageNum = parseInt(input.value);
            if (pageNum >= 1 && pageNum <= totalPages && pageNum !== this.currentPage) {
                this.currentPage = pageNum;
                this.loadThumbnails();
                window.scrollTo({ top: 0, behavior: 'smooth' });
            } else {
                input.value = this.currentPage;
            }
        });
        
        ul.appendChild(inputLi);
    }
    
    renderPageNumbers(ul, totalPages) {
        // Smart page number display
        const maxVisiblePages = 5;
        let startPage, endPage;
        
        if (totalPages <= maxVisiblePages) {
            // Show all pages
            startPage = 1;
            endPage = totalPages;
        } else {
            // Calculate range around current page
            const halfVisible = Math.floor(maxVisiblePages / 2);
            startPage = Math.max(1, this.currentPage - halfVisible);
            endPage = Math.min(totalPages, startPage + maxVisiblePages - 1);
            
            // Adjust if we're near the end
            if (endPage - startPage < maxVisiblePages - 1) {
                startPage = Math.max(1, endPage - maxVisiblePages + 1);
            }
        }
        
        // Show first page if not in range
        if (startPage > 1) {
            this.addPageButton(ul, 1, totalPages);
            if (startPage > 2) {
                const ellipsisLi = document.createElement('li');
                ellipsisLi.className = 'page-item disabled';
                ellipsisLi.innerHTML = '<span class="page-link">...</span>';
                ul.appendChild(ellipsisLi);
            }
        }
        
        // Show page numbers in range
        for (let i = startPage; i <= endPage; i++) {
            this.addPageButton(ul, i, totalPages);
        }
        
        // Show last page if not in range
        if (endPage < totalPages) {
            if (endPage < totalPages - 1) {
                const ellipsisLi = document.createElement('li');
                ellipsisLi.className = 'page-item disabled';
                ellipsisLi.innerHTML = '<span class="page-link">...</span>';
                ul.appendChild(ellipsisLi);
            }
            this.addPageButton(ul, totalPages, totalPages);
        }
    }
    
    addPageButton(ul, pageNum, totalPages) {
        const li = document.createElement('li');
        li.className = `page-item ${pageNum === this.currentPage ? 'active' : ''}`;
        li.innerHTML = `<a class="page-link" href="#">${pageNum}</a>`;
        li.addEventListener('click', (e) => {
            e.preventDefault();
            this.currentPage = pageNum;
            this.loadThumbnails();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
        ul.appendChild(li);
    }
    
    async loadStats() {
        try {
            const response = await fetch('/api/stats');
            const data = await response.json();
            
            this.statsBadge.textContent = `${data.total_thumbnails.toLocaleString()} thumbnails`;
            this.statsBadge.classList.add('stats-updating');
            setTimeout(() => this.statsBadge.classList.remove('stats-updating'), 500);
            
        } catch (error) {
            console.error('Failed to load stats:', error);
        }
    }
    
    async refreshIndex() {
        this.refreshBtn.classList.add('refreshing');
        this.refreshBtn.disabled = true;
        
        // Get selected files for indexing
        const selectedFiles = Array.from(this.selectedCacheFiles);
        const fileCount = selectedFiles.length;
        
        if (fileCount === 0) {
            this.showNotification('Warning', 'No database files selected for indexing', 'warning');
            this.refreshBtn.classList.remove('refreshing');
            this.refreshBtn.disabled = false;
            return;
        }
        
        this.showNotification('Info', `Indexing ${fileCount} database file(s)... This may take a moment.`, 'info');
        
        try {
            const response = await fetch('/api/refresh', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ selected_files: selectedFiles })
            });
            const data = await response.json();
            
            if (data.status === 'success') {
                this.showNotification('Success', `Indexed ${data.count.toLocaleString()} thumbnails from ${fileCount} file(s)`, 'success');
                // Reload filter options as they may have changed
                this.formatFilter.innerHTML = '<option value="">All Formats</option>';
                await this.loadFilterOptions();
                // Reload cache files to update indexed status
                await this.loadCacheFiles();
                this.loadThumbnails();
                this.loadStats();
            } else {
                this.showNotification('Error', data.error || 'Failed to refresh index', 'danger');
            }
            
        } catch (error) {
            console.error('Failed to refresh index:', error);
            this.showNotification('Error', 'Failed to refresh index', 'danger');
        }
        
        this.refreshBtn.classList.remove('refreshing');
        this.refreshBtn.disabled = false;
    }
    
    async exportSelected() {
        if (this.selectedIds.size === 0) {
            this.showNotification('Warning', 'No thumbnails selected', 'warning');
            return;
        }
        
        try {
            const response = await fetch('/api/export', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ids: Array.from(this.selectedIds) })
            });
            
            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `thumbnails_export_${Date.now()}.zip`;
                a.click();
                window.URL.revokeObjectURL(url);
                
                this.showNotification('Success', `Exported ${this.selectedIds.size} thumbnails`, 'success');
                this.toggleSelectMode();
            } else {
                const data = await response.json();
                this.showNotification('Error', data.error || 'Export failed', 'danger');
            }
            
        } catch (error) {
            console.error('Export failed:', error);
            this.showNotification('Error', 'Export failed', 'danger');
        }
    }
    
    async exportSingle(id) {
        try {
            const response = await fetch('/api/export', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ids: [parseInt(id)] })
            });
            
            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `thumbnail_${id}.png`;
                a.click();
                window.URL.revokeObjectURL(url);
                
                this.showNotification('Success', 'Thumbnail exported', 'success');
            }
            
        } catch (error) {
            console.error('Export failed:', error);
            this.showNotification('Error', 'Export failed', 'danger');
        }
    }
    
    showLoading(show) {
        if (show) {
            this.isLoading = true;
            this.loadingIndicator.classList.remove('d-none');
            this.gallery.classList.add('d-none');
            this.emptyState.classList.add('d-none');
            // Add fade effect
            this.loadingIndicator.style.opacity = '0';
            requestAnimationFrame(() => {
                this.loadingIndicator.style.transition = 'opacity 0.2s ease';
                this.loadingIndicator.style.opacity = '1';
            });
        } else {
            this.isLoading = false;
            this.loadingIndicator.style.opacity = '0';
            setTimeout(() => {
                this.loadingIndicator.classList.add('d-none');
                this.loadingIndicator.style.opacity = '1';
            }, 200);
        }
    }
    
    showNotification(title, message, type = 'info') {
        const toastEl = document.getElementById('notification-toast');
        // Reset classes and apply new ones
        toastEl.className = 'toast';
        toastEl.classList.add(`bg-${type}`);
        
        const titleEl = document.getElementById('toast-title');
        const messageEl = document.getElementById('toast-message');
        
        // Set icon based on type
        const icons = {
            success: 'bi-check-circle-fill',
            danger: 'bi-exclamation-circle-fill',
            warning: 'bi-exclamation-triangle-fill',
            info: 'bi-info-circle-fill'
        };
        
        titleEl.innerHTML = `<i class="bi ${icons[type] || icons.info} me-2"></i>${title}`;
        messageEl.textContent = message;
        this.toast.show();
    }
}

// Initialize the viewer when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.thumbnailViewer = new ThumbnailViewer();
});
