document.addEventListener('DOMContentLoaded', function() {
    // API Key elements
    const apiKeyInput = document.getElementById('api-key');
    const togglePasswordBtn = document.getElementById('toggle-password');
    const saveApiKeyBtn = document.getElementById('save-api-key');
    const settingsToggle = document.getElementById('settings-toggle');
    const settingsBody = document.getElementById('settings-body');
    
    // Existing elements
    const uploadForm = document.getElementById('upload-form');
    const fileInput = document.getElementById('document');
    const fileName = document.getElementById('file-name');
    const uploadContainer = document.querySelector('.upload-container');
    const resultsContainer = document.querySelector('.results-container');
    const loadingSpinner = document.getElementById('loading-spinner');
    const errorMessage = document.getElementById('error-message');
    const ocrResults = document.getElementById('ocr-results');
    const newUploadBtn = document.getElementById('new-upload-btn');

    // Preview elements
    const documentPreview = document.getElementById('document-preview');
    const previewPlaceholder = documentPreview.querySelector('.preview-placeholder');
    const previewPages = document.getElementById('document-pages');
    const prevPageBtn = document.getElementById('prev-page');
    const nextPageBtn = document.getElementById('next-page');
    const pageIndicator = document.getElementById('page-indicator');
    
    // Text control elements
    const copyTextBtn = document.getElementById('copy-text');
    const downloadTextBtn = document.getElementById('download-text');
    
    // Document preview state
    let currentPage = 1;  // Changed to start from 1
    let totalPages = 1;
    let previewUrl = '';
    let allExtractedText = '';
    let pdfDoc = null;
    let currentPreviewType = null; // 'pdf' or 'image'
    
    // Check if API key exists in localStorage
    const savedApiKey = localStorage.getItem('mistralApiKey');
    if (savedApiKey) {
        apiKeyInput.value = savedApiKey;
    } else {
        // If no API key, automatically show settings
        settingsBody.classList.add('active');
    }

    // Toggle settings visibility
    settingsToggle.addEventListener('click', function() {
        settingsBody.classList.toggle('active');
        const toggleIcon = this.querySelector('.toggle-icon');
        toggleIcon.textContent = settingsBody.classList.contains('active') ? '▲' : '▼';
    });

    // Toggle password visibility
    togglePasswordBtn.addEventListener('click', function() {
        if (apiKeyInput.type === 'password') {
            apiKeyInput.type = 'text';
            this.textContent = '🔒';
        } else {
            apiKeyInput.type = 'password';
            this.textContent = '👁️';
        }
    });

    // Save API key
    saveApiKeyBtn.addEventListener('click', function() {
        const apiKey = apiKeyInput.value.trim();
        if (apiKey) {
            localStorage.setItem('mistralApiKey', apiKey);
            alert('API key saved successfully!');
            
            // Close settings panel
            settingsBody.classList.remove('active');
            settingsToggle.querySelector('.toggle-icon').textContent = '▼';
        } else {
            alert('Please enter a valid API key.');
        }
    });

    // Display filename when selected
    fileInput.addEventListener('change', function() {
        if (this.files && this.files.length > 0) {
            fileName.textContent = this.files[0].name;
        } else {
            fileName.textContent = '';
        }
    });

    // Handle drag and drop
    const dropArea = fileInput.nextElementSibling;
    
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropArea.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, unhighlight, false);
    });

    function highlight() {
        dropArea.classList.add('highlight');
    }

    function unhighlight() {
        dropArea.classList.remove('highlight');
    }

    dropArea.addEventListener('drop', handleDrop, false);

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        fileInput.files = files;
        
        if (files && files.length > 0) {
            fileName.textContent = files[0].name;
        }
    }

    // Handle form submission
    uploadForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        // Check if API key is available
        const apiKey = localStorage.getItem('mistralApiKey');
        if (!apiKey) {
            showError('Please enter your Mistral AI API key in the settings section.');
            settingsBody.classList.add('active');
            settingsToggle.querySelector('.toggle-icon').textContent = '▲';
            return;
        }
        
        if (!fileInput.files || fileInput.files.length === 0) {
            showError('Please select a file to upload.');
            return;
        }

        // Reset preview state
        currentPage = 0;
        totalPages = 1;
        previewUrl = '';
        allExtractedText = '';
        pdfDoc = null;
        
        // Show results container and loading spinner
        uploadContainer.style.display = 'none';
        resultsContainer.style.display = 'block';
        loadingSpinner.style.display = 'flex';
        errorMessage.style.display = 'none';
        ocrResults.innerHTML = '';
        
        // Clear preview area
        previewPlaceholder.style.display = 'flex';
        previewPages.style.display = 'none';
        previewPages.innerHTML = '';
        
        // Create form data
        const formData = new FormData();
        formData.append('document', fileInput.files[0]);
        formData.append('api_key', apiKey);  // Send API key to server
        formData.append('include_images', 'true');  // Request images to be included in response
        
        // Send request to the server
        fetch('/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(data => {
                    throw new Error(data.error || 'Error processing document');
                });
            }
            return response.json();
        })
        .then(data => {
            loadingSpinner.style.display = 'none';
            
            // Set up document preview if available
            if (data.preview_file) {
                previewUrl = data.preview_file;
                setupDocumentPreview(previewUrl, fileInput.files[0].type);
            }
            
            // Display OCR results
            displayResults(data);
        })
        .catch(error => {
            loadingSpinner.style.display = 'none';
            showError(error.message);
        });
    });

    function setupDocumentPreview(url, fileType) {
        previewPlaceholder.style.display = 'none';
        previewPages.style.display = 'block';
        previewPages.innerHTML = ''; // Clear existing content
        currentPreviewType = fileType.startsWith('image/') ? 'image' : 'pdf';
        
        if (fileType === 'application/pdf') {
            // Load PDF.js if not already loaded
            if (!window.pdfjsLib) {
                const script = document.createElement('script');
                script.src = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.4.120/pdf.min.js';
                script.onload = () => {
                    window.pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.4.120/pdf.worker.min.js';
                    loadPdfPreview(url);
                };
                document.head.appendChild(script);
            } else {
                loadPdfPreview(url);
            }
        } else if (fileType.startsWith('image/')) {
            // Image preview
            const img = new Image();
            img.onload = function() {
                previewPages.innerHTML = `
                    <div class="preview-page" style="display: block">
                        <img src="${url}" alt="Document preview">
                    </div>
                `;
                currentPage = 1;
                totalPages = 1;
                updatePageControls();
            };
            img.onerror = function() {
                showError('Error loading image preview');
            };
            img.src = url;
        }
    }
    
    function loadPdfPreview(url) {
        const loadingTask = pdfjsLib.getDocument(url);
        
        loadingTask.promise.then(pdf => {
            pdfDoc = pdf;
            totalPages = pdf.numPages;
            currentPage = 1;
            
            // Render first page
            renderPdfPage(currentPage);
            updatePageControls();
        }).catch(error => {
            showError(`Error loading PDF preview: ${error.message}`);
        });
    }
    
    function renderPdfPage(pageNumber) {
        if (!pdfDoc) return;
        
        // Show loading state
        previewPages.innerHTML = '<div class="loading-page">Loading page...</div>';
        
        pdfDoc.getPage(pageNumber).then(page => {
            const viewport = page.getViewport({ scale: 1.0 });
            const canvas = document.createElement('canvas');
            const context = canvas.getContext('2d');
            
            // Set canvas dimensions to match page size
            const maxWidth = documentPreview.clientWidth - 40; // Account for padding
            const scale = Math.min(maxWidth / viewport.width, 1.0);
            const scaledViewport = page.getViewport({ scale });
            
            canvas.width = scaledViewport.width;
            canvas.height = scaledViewport.height;
            
            // Render PDF page into canvas context
            const renderContext = {
                canvasContext: context,
                viewport: scaledViewport
            };
            
            const renderTask = page.render(renderContext);
            
            renderTask.promise.then(() => {
                previewPages.innerHTML = '';
                const pageContainer = document.createElement('div');
                pageContainer.className = 'preview-page';
                pageContainer.appendChild(canvas);
                previewPages.appendChild(pageContainer);
            }).catch(error => {
                showError(`Error rendering PDF page: ${error.message}`);
            });
        });
    }
    
    function updatePageControls() {
        // Only show page controls if we have a PDF with multiple pages
        const showControls = currentPreviewType === 'pdf' && totalPages > 1;
        
        document.querySelector('.page-controls').style.display = showControls ? 'flex' : 'none';
        
        if (showControls) {
            pageIndicator.textContent = `Page ${currentPage} of ${totalPages}`;
            prevPageBtn.disabled = currentPage <= 1;
            nextPageBtn.disabled = currentPage >= totalPages;
        }
        
        // Update corresponding text section
        const ocrPages = document.querySelectorAll('.ocr-page');
        ocrPages.forEach((page, index) => {
            page.style.display = (index + 1 === currentPage) ? 'block' : 'none';
        });
    }
    
    // Update page navigation event listeners
    prevPageBtn.onclick = () => {
        if (currentPreviewType === 'pdf' && currentPage > 1) {
            currentPage--;
            renderPdfPage(currentPage);
            updatePageControls();
            // Scroll to corresponding text section
            const targetPage = document.getElementById(`page-${currentPage}`);
            if (targetPage) {
                targetPage.scrollIntoView({ behavior: 'smooth' });
            }
        }
    };
    
    nextPageBtn.onclick = () => {
        if (currentPreviewType === 'pdf' && currentPage < totalPages) {
            currentPage++;
            renderPdfPage(currentPage);
            updatePageControls();
            // Scroll to corresponding text section
            const targetPage = document.getElementById(`page-${currentPage}`);
            if (targetPage) {
                targetPage.scrollIntoView({ behavior: 'smooth' });
            }
        }
    };

    function displayResults(data) {
        console.log("OCR Response:", data);
        let resultHtml = '';
        allExtractedText = '';
        
        if (data.debug_info) {
            console.log("Debug info:", data.debug_info);
            resultHtml += `<div class="debug-info">
                <h4>Debug Information</h4>
                <pre>${JSON.stringify(data.debug_info, null, 2)}</pre>
            </div>`;
        }
        
        if (data.pages && data.pages.length > 0) {
            data.pages.forEach((page, index) => {
                const isCurrentPage = index + 1 === currentPage;
                resultHtml += `<div class="ocr-page markdown-content" id="page-${index + 1}" style="display: ${isCurrentPage ? 'block' : 'none'}">`;
                resultHtml += `<h3 class="page-heading">Page ${index + 1}</h3>`;
                
                if (page.markdown && page.markdown.trim()) {
                    // Convert markdown to HTML while preserving image references
                    const tempDiv = document.createElement('div');
                    tempDiv.innerHTML = marked.parse(page.markdown);
                    
                    // Process any base64 images in the markdown
                    const imgElements = tempDiv.getElementsByTagName('img');
                    Array.from(imgElements).forEach(img => {
                        const src = img.getAttribute('src');
                        if (src && src.startsWith('data:')) {
                            img.classList.add('inline-image');
                            img.setAttribute('alt', img.getAttribute('alt') || 'Inline document image');
                        }
                    });
                    
                    resultHtml += `<div class="page-text">${tempDiv.innerHTML}</div>`;
                    allExtractedText += page.text + '\n\n';
                } else if (page.text && page.text.trim()) {
                    // Handle legacy format or raw text
                    if (page.text.startsWith('Raw OCR output:')) {
                        resultHtml += `<div class="raw-ocr">
                            <p class="note">Raw OCR output is shown below:</p>
                            <pre class="raw-text">${page.text}</pre>
                        </div>`;
                    } else {
                        resultHtml += `<div class="page-text"><pre>${page.text}</pre></div>`;
                    }
                    allExtractedText += page.text + '\n\n';
                } else {
                    resultHtml += '<p class="no-text-message">No text found on this page</p>';
                }
                
                // Add any additional images that weren't part of the markdown
                if (page.images && page.images.length > 0) {
                    resultHtml += '<div class="additional-images">';
                    page.images.forEach(img => {
                        if (img.image_base64 && !page.markdown.includes(img.image_base64)) {
                            resultHtml += `
                                <figure class="image-figure">
                                    <img src="data:image/png;base64,${img.image_base64}" 
                                         alt="${img.text || 'Document image'}"
                                         class="document-image">
                                    ${img.text ? `<figcaption>${img.text}</figcaption>` : ''}
                                </figure>
                            `;
                        }
                    });
                    resultHtml += '</div>';
                }
                
                resultHtml += '</div>';
            });
        } else {
            resultHtml += '<p>No text or images were extracted from the document.</p>';
        }
        
        ocrResults.innerHTML = resultHtml;
        
        // If we have extracted text, enable the copy and download buttons
        if (allExtractedText.trim()) {
            copyTextBtn.disabled = false;
            downloadTextBtn.disabled = false;
            downloadMarkdownBtn.disabled = false;
            downloadDocxBtn.disabled = false;
        } else {
            copyTextBtn.disabled = true;
            downloadTextBtn.disabled = true;
            downloadMarkdownBtn.disabled = true;
            downloadDocxBtn.disabled = true;
        }
        
        // Set up page navigation synchronization
        setupPageSync(data.pages ? data.pages.length : 0);
        
        // Setup copy and download buttons
        setupTextControls();
    }

    function setupPageSync(numPages) {
        // If PDF has multiple pages, update page controls
        if (numPages > 1 && pdfDoc) {
            // Add scroll event listeners to synchronize PDF view with text
            ocrResults.addEventListener('scroll', () => {
                // Find which page is in view
                const pageElements = ocrResults.querySelectorAll('.ocr-page');
                let visiblePage = 1;
                
                pageElements.forEach((page, index) => {
                    const rect = page.getBoundingClientRect();
                    if (rect.top <= window.innerHeight / 2 && rect.bottom >= window.innerHeight / 2) {
                        visiblePage = index + 1;
                    }
                });
                
                if (visiblePage !== currentPage) {
                    currentPage = visiblePage;
                    renderPdfPage(currentPage);
                    updatePageControls();
                }
            });
            
            // Add click handlers to page headings
            document.querySelectorAll('.page-heading').forEach((heading, index) => {
                heading.addEventListener('click', () => {
                    currentPage = index + 1;
                    renderPdfPage(currentPage);
                    updatePageControls();
                });
            });
        }
    }
    
    function setupTextControls() {
        // Copy button
        copyTextBtn.addEventListener('click', () => {
            navigator.clipboard.writeText(allExtractedText).then(() => {
                const originalText = copyTextBtn.textContent;
                copyTextBtn.textContent = '✓ Copied!';
                setTimeout(() => {
                    copyTextBtn.textContent = originalText;
                }, 2000);
            }).catch(err => {
                showError('Failed to copy text: ' + err);
            });
        });
        
        // Download button
        downloadTextBtn.addEventListener('click', () => {
            const blob = new Blob([allExtractedText], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'extracted_text.txt';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        });
    }
    
    function showError(message) {
        errorMessage.textContent = message;
        errorMessage.style.display = 'block';
    }
    
    // New upload button
    newUploadBtn.addEventListener('click', function() {
        uploadContainer.style.display = 'block';
        resultsContainer.style.display = 'none';
        fileInput.value = '';
        fileName.textContent = '';
    });

    // Batch processing elements
    const fileList = document.getElementById('file-list');
    const batchModeCheckbox = document.getElementById('batch-mode');
    const progressIndicator = document.getElementById('progress-indicator');
    const progressText = document.getElementById('progress-text');
    const processingStatus = document.getElementById('processing-status');
    
    // File list management
    fileInput.addEventListener('change', function() {
        const files = Array.from(this.files);
        updateFileList(files);
    });
    
    function updateFileList(files) {
        fileList.innerHTML = '';
        if (files.length > 0) {
            const listContainer = document.createElement('div');
            listContainer.className = 'file-list';
            
            files.forEach((file, index) => {
                const item = document.createElement('div');
                item.className = 'file-item';
                
                const name = document.createElement('span');
                name.className = 'file-name';
                name.textContent = file.name;
                
                const removeBtn = document.createElement('button');
                removeBtn.className = 'file-remove';
                removeBtn.textContent = '×';
                removeBtn.onclick = () => {
                    const newFiles = new DataTransfer();
                    Array.from(fileInput.files)
                        .filter((_, i) => i !== index)
                        .forEach(file => newFiles.items.add(file));
                    fileInput.files = newFiles.files;
                    updateFileList(Array.from(fileInput.files));
                };
                
                item.appendChild(name);
                item.appendChild(removeBtn);
                listContainer.appendChild(item);
            });
            
            fileList.appendChild(listContainer);
        }
    }
    
    // Handle form submission with batch processing
    uploadForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        // Check if API key is available
        const apiKey = localStorage.getItem('mistralApiKey');
        if (!apiKey) {
            showError('Please enter your Mistral AI API key in the settings section.');
            settingsBody.classList.add('active');
            settingsToggle.querySelector('.toggle-icon').textContent = '▲';
            return;
        }
        
        if (!fileInput.files || fileInput.files.length === 0) {
            showError('Please select at least one file to upload.');
            return;
        }
        
        // Reset UI state
        resetUI();
        
        const files = Array.from(fileInput.files);
        const useBatchProcessing = batchModeCheckbox.checked && files.length > 1;
        
        try {
            if (useBatchProcessing) {
                // Batch processing
                const formData = new FormData();
                files.forEach(file => {
                    formData.append('documents[]', file);
                });
                formData.append('api_key', apiKey);
                
                // Start batch processing
                const response = await fetch('/batch-upload', {
                    method: 'POST',
                    body: formData
                });
                
                if (!response.ok) {
                    const data = await response.json();
                    throw new Error(data.error || 'Error starting batch processing');
                }
                
                const { job_id, total_files } = await response.json();
                await pollBatchStatus(job_id, apiKey, total_files);
                
            } else {
                // Single file or sequential processing
                for (const file of files) {
                    const formData = new FormData();
                    formData.append('document', file);
                    formData.append('api_key', apiKey);
                    formData.append('include_images', 'true');
                    
                    updateProgress(files.indexOf(file), files.length);
                    processingStatus.textContent = `Processing ${file.name}...`;
                    
                    const response = await fetch('/upload', {
                        method: 'POST',
                        body: formData
                    });
                    
                    if (!response.ok) {
                        const data = await response.json();
                        throw new Error(data.error || 'Error processing document');
                    }
                    
                    const result = await response.json();
                    displayResults(result, file.name);
                }
                
                updateProgress(files.length, files.length);
                processingStatus.textContent = 'Processing completed!';
            }
            
        } catch (error) {
            showError(error.message);
            loadingSpinner.style.display = 'none';
        }
    });
    
    async function pollBatchStatus(jobId, apiKey, totalFiles) {
        const pollInterval = 2000; // 2 seconds
        
        while (true) {
            const response = await fetch(`/batch-status/${jobId}?api_key=${apiKey}`);
            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.error || 'Error checking batch status');
            }
            
            const status = await response.json();
            
            if (status.status === 'completed') {
                // Display all results
                displayBatchResults(status.results);
                updateProgress(totalFiles, totalFiles);
                processingStatus.textContent = 'Batch processing completed!';
                break;
            } else if (status.status === 'failed') {
                throw new Error('Batch processing failed');
            } else {
                // Update progress
                const progress = status.progress;
                updateProgress(progress.succeeded + progress.failed, progress.total);
                processingStatus.textContent = `Processing batch... ${progress.succeeded}/${progress.total} completed`;
                await new Promise(resolve => setTimeout(resolve, pollInterval));
            }
        }
    }
    
    function updateProgress(current, total) {
        const percentage = (current / total) * 100;
        progressIndicator.style.width = `${percentage}%`;
        progressText.textContent = `${current} / ${total} files processed`;
    }
    
    function resetUI() {
        uploadContainer.style.display = 'none';
        resultsContainer.style.display = 'block';
        loadingSpinner.style.display = 'flex';
        errorMessage.style.display = 'none';
        ocrResults.innerHTML = '';
        
        // Reset preview area
        previewPlaceholder.style.display = 'flex';
        previewPages.style.display = 'none';
        previewPages.innerHTML = '';
        
        // Reset progress
        progressIndicator.style.width = '0%';
        progressText.textContent = '0 / 0 files processed';
        processingStatus.textContent = 'Starting processing...';
    }
    
    function displayBatchResults(results) {
        ocrResults.innerHTML = '';
        const batchResultsContainer = document.createElement('div');
        batchResultsContainer.className = 'batch-results';
        
        results.forEach(result => {
            const resultCard = document.createElement('div');
            resultCard.className = 'batch-item';
            
            const header = document.createElement('div');
            header.className = 'batch-item-header';
            header.innerHTML = `
                <h4>Result ${result.custom_id}</h4>
                <div class="metadata">
                    <span>Language: ${result.result.metadata.languages.join(', ') || 'Unknown'}</span>
                    <span>Topics: ${result.result.metadata.topics.join(', ') || 'None detected'}</span>
                </div>
            `;
            
            const content = document.createElement('div');
            content.className = 'batch-item-content markdown-content';
            
            // Combine all page content
            const allText = result.result.pages
                .map(page => page.markdown || page.text)
                .join('\n\n');
            
            content.innerHTML = marked.parse(allText);
            
            resultCard.appendChild(header);
            resultCard.appendChild(content);
            batchResultsContainer.appendChild(resultCard);
        });
        
        ocrResults.appendChild(batchResultsContainer);
        loadingSpinner.style.display = 'none';
    }

    // Font size controls
    const decreaseFontBtn = document.getElementById('decrease-font');
    const resetFontBtn = document.getElementById('reset-font');
    const increaseFontBtn = document.getElementById('increase-font');
    const textContent = document.querySelector('.text-content');
    
    // Download format buttons
    const downloadMarkdownBtn = document.getElementById('download-markdown');
    const downloadDocxBtn = document.getElementById('download-docx');
    
    // Font size control (stored in CSS variable)
    let currentFontSize = 14;
    const minFontSize = 10;
    const maxFontSize = 24;
    const fontSizeStep = 2;
    
    function updateFontSize(size) {
        textContent.style.setProperty('--content-font-size', `${size}px`);
        
        // Store preference
        localStorage.setItem('preferredFontSize', size);
        
        // Update button states
        decreaseFontBtn.disabled = size <= minFontSize;
        increaseFontBtn.disabled = size >= maxFontSize;
    }
    
    // Load preferred font size
    const savedFontSize = localStorage.getItem('preferredFontSize');
    if (savedFontSize) {
        currentFontSize = parseInt(savedFontSize);
        updateFontSize(currentFontSize);
    }
    
    // Font size control event listeners
    decreaseFontBtn.addEventListener('click', () => {
        if (currentFontSize > minFontSize) {
            currentFontSize -= fontSizeStep;
            updateFontSize(currentFontSize);
        }
    });
    
    resetFontBtn.addEventListener('click', () => {
        currentFontSize = 14;
        updateFontSize(currentFontSize);
    });
    
    increaseFontBtn.addEventListener('click', () => {
        if (currentFontSize < maxFontSize) {
            currentFontSize += fontSizeStep;
            updateFontSize(currentFontSize);
        }
    });
    
    // Download format handlers
    downloadMarkdownBtn.addEventListener('click', () => {
        // Create markdown version
        let markdownContent = '';
        document.querySelectorAll('.ocr-page').forEach((page, index) => {
            if (index > 0) markdownContent += '\n\n---\n\n';
            markdownContent += `# Page ${index + 1}\n\n`;
            
            // Get the page's markdown content if available, otherwise use text
            const pageData = data.pages[index];
            markdownContent += pageData.markdown || pageData.text;
        });
        
        // Download as .md file
        const blob = new Blob([markdownContent], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'ocr_results.md';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    });
    
    downloadDocxBtn.addEventListener('click', async () => {
        try {
            const formData = new FormData();
            formData.append('content', allExtractedText);
            
            const response = await fetch('/download/docx', {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) throw new Error('Failed to generate DOCX file');
            
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'ocr_results.docx';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            
        } catch (error) {
            showError('Failed to generate DOCX file: ' + error.message);
        }
    });
});