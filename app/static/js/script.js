// Loading overlay functions
const loadingOverlay = document.querySelector('.loading-overlay');

function showLoading() {
    loadingOverlay.style.display = 'flex';
}

function hideLoading() {
    loadingOverlay.style.display = 'none';
}

// File upload handling
document.addEventListener('DOMContentLoaded', function() {
    const uploadForm = document.getElementById('uploadForm');
    const fileInput = document.getElementById('fileInput');
    const preview = document.getElementById('preview');
    const result = document.getElementById('result');
    const copyButton = document.getElementById('copyButton');
    const uploadSection = document.querySelector('.upload-section');

    if (!uploadSection) return; // Exit if we're not on the upload page

    // Handle drag and drop events
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        uploadSection.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    // Add highlighting when dragging over
    ['dragenter', 'dragover'].forEach(eventName => {
        uploadSection.addEventListener(eventName, () => {
            uploadSection.classList.add('highlight');
        });
    });

    // Remove highlighting when leaving or dropping
    ['dragleave', 'drop'].forEach(eventName => {
        uploadSection.addEventListener(eventName, () => {
            uploadSection.classList.remove('highlight');
        });
    });

    // Handle file drop
    uploadSection.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;

        if (files.length > 0) {
            fileInput.files = files;
            // Show preview immediately
            updatePreview(files[0]);
        }
    });

    // Handle file selection via input
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            // Show preview immediately
            updatePreview(fileInput.files[0]);
        }
    });

    // Function to update preview
    function updatePreview(file) {
        if (file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = function(e) {
                preview.innerHTML = `<img src="${e.target.result}" alt="Preview">`;
            };
            reader.readAsDataURL(file);
        } else {
            preview.innerHTML = `<div class="text-center text-muted">
                <i class="bi bi-file-pdf display-1"></i>
                <p>PDF document loaded</p>
            </div>`;
        }
    }

    // Handle form submission
    uploadForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        if (!fileInput.files.length) {
            alert('Please select a file first.');
            return;
        }

        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        
        showLoading();

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Error processing document');
            }
            
            if (data.error) {
                throw new Error(data.error);
            }
            
            // Display markdown result
            result.innerHTML = marked.parse(data.markdown);
            if (copyButton) copyButton.style.display = 'block';
            
        } catch (error) {
            console.error('Error:', error);
            result.innerHTML = `<div class="alert alert-danger">
                <i class="bi bi-exclamation-triangle"></i> 
                Error processing document: ${error.message}
            </div>`;
        } finally {
            hideLoading();
        }
    });

    // Handle copy button
    if (copyButton) {
        copyButton.addEventListener('click', function() {
            const markdown = result.textContent;
            navigator.clipboard.writeText(markdown).then(function() {
                const originalText = copyButton.innerHTML;
                copyButton.innerHTML = '<i class="bi bi-check"></i> Copied!';
                setTimeout(() => {
                    copyButton.innerHTML = originalText;
                }, 2000);
            });
        });
    }
}); 