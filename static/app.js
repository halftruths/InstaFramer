document.addEventListener('DOMContentLoaded', () => {
    // State
    let currentSourcePath = null;
    let isSourceDir = false;
    let currentBrowserPath = null;
    let currentPreviewImage = null;
    let previewController = new AbortController();

    // UI Elements
    const elements = {
        // Tabs
        tabs: document.querySelectorAll('.tab-btn'),

        // Controls
        browseBtn: document.getElementById('browse-btn'),
        amazonUrlInput: document.getElementById('amazon-url-input'),
        amazonImportBtn: document.getElementById('amazon-import-btn'),
        selectedPath: document.getElementById('selected-source-path'),
        folderGalleryGroup: document.getElementById('folder-gallery-group'),
        folderImageList: document.getElementById('folder-image-list'),
        aspectRatio: document.getElementById('aspect-ratio'),

        innerBorderWidth: document.getElementById('inner-border-width'),
        innerBorderVal: document.getElementById('inner-border-val'),
        innerBorderColor: document.getElementById('inner-border-color'),
        innerBorderHex: document.getElementById('inner-border-hex'),

        outerBorderWidth: document.getElementById('outer-border-width'),
        outerBorderVal: document.getElementById('outer-border-val'),
        outerBorderColor: document.getElementById('outer-border-color'),
        outerBorderHex: document.getElementById('outer-border-hex'),

        batchBtn: document.getElementById('batch-process-btn'),
        processStatus: document.getElementById('process-status'),

        // Preview
        livePreview: document.getElementById('live-preview-img'),
        previewPlaceholder: document.getElementById('preview-placeholder'),
        loadingSpinner: document.getElementById('loading-spinner'),
        previewBadge: document.getElementById('preview-badge'),

        // Modal
        modal: document.getElementById('file-browser-modal'),
        closeModal: document.getElementById('close-modal'),
        upDirBtn: document.getElementById('up-dir-btn'),
        currentPathInput: document.getElementById('current-path-input'),
        fileList: document.getElementById('file-list'),
        selectFolderBtn: document.getElementById('select-folder-btn')
    };

    // --- Initialization ---

    // Tabs functionality
    elements.tabs.forEach(tab => {
        tab.addEventListener('click', (e) => {
            elements.tabs.forEach(t => t.classList.remove('active'));
            e.target.classList.add('active');

            if (e.target.dataset.tab === 'advanced') {
                document.body.classList.add('mode-advanced');
            } else {
                document.body.classList.remove('mode-advanced');
            }
        });
    });

    // Input Syncing (Slider <-> Text)
    const syncInputs = (slider, valDisplay, colorInput, hexInput) => {
        slider.addEventListener('input', (e) => {
            valDisplay.textContent = `${e.target.value}px`;
            schedulePreviewUpdate();
        });

        colorInput.addEventListener('input', (e) => {
            hexInput.value = e.target.value;
            schedulePreviewUpdate();
        });

        hexInput.addEventListener('change', (e) => {
            if (/^#[0-9A-F]{6}$/i.test(e.target.value)) {
                colorInput.value = e.target.value;
                schedulePreviewUpdate();
            } else {
                e.target.value = colorInput.value; // revert if invalid
            }
        });
    };

    syncInputs(elements.innerBorderWidth, elements.innerBorderVal, elements.innerBorderColor, elements.innerBorderHex);
    syncInputs(elements.outerBorderWidth, elements.outerBorderVal, elements.outerBorderColor, elements.outerBorderHex);

    elements.aspectRatio.addEventListener('change', schedulePreviewUpdate);

    // --- File Browser Modal ---

    elements.browseBtn.addEventListener('click', () => {
        elements.modal.style.display = 'flex';
        loadFileBrowser();
    });

    elements.closeModal.addEventListener('click', () => {
        elements.modal.style.display = 'none';
    });

    elements.upDirBtn.addEventListener('click', () => {
        const parentPath = elements.fileList.querySelector('.file-item[data-name=".."]')?.dataset.path;
        if (parentPath) {
            loadFileBrowser(parentPath);
        }
    });

    elements.selectFolderBtn.addEventListener('click', () => {
        setMainSource(currentBrowserPath, true);
        elements.modal.style.display = 'none';
    });

    // --- Amazon Import ---
    elements.amazonImportBtn.addEventListener('click', async () => {
        const url = elements.amazonUrlInput.value.trim();
        if (!url) return;

        elements.amazonImportBtn.disabled = true;
        const origText = elements.amazonImportBtn.textContent;
        elements.amazonImportBtn.textContent = 'Scraping Photos...';

        try {
            const res = await fetch('/api/amazon', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });
            const data = await res.json();

            if (!res.ok) throw new Error(data.detail || 'Amazon Import Failed');

            // Set the cache directory as the current source
            setMainSource(data.cache_dir, true);
            elements.amazonUrlInput.value = '';
        } catch (err) {
            console.error(err);
            alert(err.message);
        } finally {
            elements.amazonImportBtn.disabled = false;
            elements.amazonImportBtn.textContent = origText;
        }
    });

    async function loadFileBrowser(path = null) {
        try {
            elements.fileList.innerHTML = '<div style="text-align:center; padding: 20px;">Loading...</div>';

            const url = path ? `/api/files?path=${encodeURIComponent(path)}` : '/api/files';
            const res = await fetch(url);

            if (!res.ok) throw new Error("Failed to load directory");

            const data = await res.json();
            currentBrowserPath = data.current_path;
            elements.currentPathInput.value = data.current_path;

            renderFileList(data.items);

        } catch (err) {
            elements.fileList.innerHTML = `<div style="color:var(--danger-color); padding: 20px;">Error: ${err.message}</div>`;
        }
    }

    function renderFileList(items) {
        elements.fileList.innerHTML = '';

        items.forEach(item => {
            const el = document.createElement('div');
            el.className = 'file-item';
            el.dataset.path = item.path;
            el.dataset.name = item.name;
            el.dataset.isdir = item.is_dir;

            const icon = item.is_dir ? '📁' : '🖼️';
            el.innerHTML = `<span class="file-icon">${icon}</span> <span>${item.name}</span>`;

            el.addEventListener('click', () => {
                // visual selection
                elements.fileList.querySelectorAll('.file-item').forEach(i => i.classList.remove('selected'));
                el.classList.add('selected');
            });

            el.addEventListener('dblclick', () => {
                if (item.is_dir) {
                    loadFileBrowser(item.path);
                } else if (item.is_image) {
                    setMainSource(item.path, false);
                    elements.modal.style.display = 'none';
                }
            });

            elements.fileList.appendChild(el);
        });
    }

    // --- Main App Logic ---

    function setMainSource(path, isDir) {
        currentSourcePath = path;
        isSourceDir = isDir;

        const shortName = path.split(/[\/\\]/).pop();
        elements.selectedPath.textContent = shortName || path;
        elements.selectedPath.title = path;

        if (isDir) {
            elements.batchBtn.disabled = false;
            elements.batchBtn.textContent = 'Batch Process Folder';
            elements.previewBadge.textContent = 'Select Image from Gallery';
            elements.livePreview.style.display = 'none';
            elements.previewPlaceholder.style.display = 'flex';
            elements.previewPlaceholder.innerHTML = `<div class="placeholder-icon">📁</div><p>Folder selected for batch processing.<br>Select an image below to preview.</p>`;

            if (elements.folderGalleryGroup) elements.folderGalleryGroup.style.display = 'flex';
            loadFolderGallery(path);
        } else {
            elements.batchBtn.disabled = false;
            elements.batchBtn.textContent = 'Process Single File';
            if (elements.folderGalleryGroup) elements.folderGalleryGroup.style.display = 'none';
            currentPreviewImage = path;
            updatePreview();
        }
    }

    async function loadFolderGallery(folderPath) {
        if (!elements.folderImageList) return;
        elements.folderImageList.innerHTML = '<div style="font-size:12px; color:var(--text-muted); padding:4px;">Loading...</div>';

        try {
            const res = await fetch(`/api/files?path=${encodeURIComponent(folderPath)}`);
            if (!res.ok) throw new Error("Failed to load folder contents");

            const data = await res.json();
            const images = data.items.filter(item => item.is_image);

            elements.folderImageList.innerHTML = '';

            if (images.length === 0) {
                elements.folderImageList.innerHTML = '<div style="font-size:12px; color:var(--text-muted); padding:4px;">No images found in folder.</div>';
                return;
            }

            images.forEach((img, idx) => {
                const el = document.createElement('div');
                el.className = 'folder-image-item';
                el.title = img.name;
                el.innerHTML = `🖼️ <span style="text-overflow:ellipsis; overflow:hidden;">${img.name}</span>`;

                el.addEventListener('click', () => {
                    elements.folderImageList.querySelectorAll('.folder-image-item').forEach(i => i.classList.remove('active'));
                    el.classList.add('active');
                    currentPreviewImage = img.path;
                    updatePreview();
                });

                elements.folderImageList.appendChild(el);
            });

            // Auto-select first image
            if (images.length > 0) {
                const firstEl = elements.folderImageList.querySelector('.folder-image-item');
                firstEl.click();
            }

        } catch (err) {
            elements.folderImageList.innerHTML = `<div style="font-size:12px; color:var(--danger-color); padding:4px;">Error: ${err.message}</div>`;
        }
    }

    // Debounce preview requests
    let previewTimeout;
    function schedulePreviewUpdate() {
        if (!currentPreviewImage) return;

        clearTimeout(previewTimeout);
        previewTimeout = setTimeout(updatePreview, 300); // 300ms debounce
    }

    async function updatePreview() {
        if (!currentPreviewImage) return;

        // Abort previous request
        previewController.abort();
        previewController = new AbortController();

        elements.loadingSpinner.style.display = 'block';
        elements.previewBadge.textContent = 'Generating...';
        elements.previewBadge.style.color = 'var(--accent-color)';

        try {
            const params = new URLSearchParams({
                image_path: currentPreviewImage,
                border_inner_width: elements.innerBorderWidth.value,
                border_inner_color: elements.innerBorderColor.value,
                border_outer_width: elements.outerBorderWidth.value,
                border_outer_color: elements.outerBorderColor.value,
                aspect_ratio: elements.aspectRatio.value,
                fit_instagram: 'true'
            });

            // We fetch the image as a blob
            const res = await fetch(`/api/preview?${params.toString()}`, {
                signal: previewController.signal
            });

            if (!res.ok) throw new Error("Preview generation failed");

            const blob = await res.blob();
            const objectUrl = URL.createObjectURL(blob);

            // Update UI
            elements.livePreview.onload = () => {
                URL.revokeObjectURL(elements.livePreview.src); // cleanup old URL
            };

            elements.livePreview.src = objectUrl;
            elements.livePreview.style.display = 'block';
            elements.previewPlaceholder.style.display = 'none';

            elements.loadingSpinner.style.display = 'none';
            elements.previewBadge.textContent = 'Live Preview';
            elements.previewBadge.style.color = 'var(--success-color)';

        } catch (err) {
            if (err.name !== 'AbortError') {
                console.error(err);
                elements.loadingSpinner.style.display = 'none';
                elements.previewBadge.textContent = 'Error';
                elements.previewBadge.style.color = 'var(--danger-color)';
            }
        }
    }

    // Process Button
    elements.batchBtn.addEventListener('click', async () => {
        if (!currentSourcePath) return;

        elements.batchBtn.disabled = true;
        const originalText = elements.batchBtn.textContent;
        elements.batchBtn.textContent = 'Processing...';
        elements.processStatus.textContent = '';
        elements.processStatus.style.color = 'var(--text-main)';

        try {
            // Determine output folder (brother to input folder or input file)
            let outFolder = '';
            if (isSourceDir) {
                outFolder = currentSourcePath + '_framed';
            } else {
                const parts = currentSourcePath.split(/[\/\\]/);
                parts.pop();
                outFolder = parts.join('/') + '/ig_framed';
            }

            const reqData = {
                input_folder: isSourceDir ? currentSourcePath : currentSourcePath.substring(0, currentSourcePath.lastIndexOf('\\')), // Very basic backup
                output_folder: outFolder,
                border_inner_width: parseInt(elements.innerBorderWidth.value),
                border_inner_color: elements.innerBorderColor.value,
                border_outer_width: parseInt(elements.outerBorderWidth.value),
                border_outer_color: elements.outerBorderColor.value,
                aspect_ratio: elements.aspectRatio.value,
                fit_instagram: true
            };

            // If single file, we'll actually let the batch API process the parent folder but... wait
            // Better to have API process just the file. For now, the API only takes folders. 
            // In a full prod app we'd split the route. Let's send the folder and it will process all in the folder if they select a file...
            // Actually, wait, let's fix backend or just tell user this processes the whole folder of the selected file.
            if (!isSourceDir) {
                elements.processStatus.textContent = "Processing the folder containing this file...";
            }

            const res = await fetch('/api/batch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(reqData)
            });

            const data = await res.json();

            if (!res.ok) throw new Error(data.detail || "Processing failed");

            elements.processStatus.textContent = `Completed ${data.processed_count} images to ${data.output_folder}`;
            elements.processStatus.style.color = 'var(--success-color)';

        } catch (err) {
            console.error(err);
            elements.processStatus.textContent = err.message;
            elements.processStatus.style.color = 'var(--danger-color)';
        } finally {
            elements.batchBtn.disabled = false;
            elements.batchBtn.textContent = originalText;
        }
    });
});
