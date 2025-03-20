import os
from flask import Blueprint, render_template, request, jsonify, current_app
from werkzeug.utils import secure_filename
from .services.mistral_service import mistral_service
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

main = Blueprint('main', __name__)

def ensure_upload_dir():
    """Ensure the upload directory exists."""
    upload_dir = os.path.join(current_app.instance_path, 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir

@main.route('/')
def index():
    has_api_key = bool(mistral_service.api_key)
    return render_template('index.html', has_api_key=has_api_key)

@main.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        api_key = request.form.get('api_key')
        if api_key:
            mistral_service.save_api_key(api_key)
            return jsonify({'success': True})
        return jsonify({'error': 'API key is required'}), 400
    return render_template('settings.html')

@main.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400

        file = request.files['file']
        if not file.filename:
            return jsonify({'error': 'No file selected'}), 400

        # Secure the filename and create upload directory
        filename = secure_filename(file.filename)
        upload_dir = ensure_upload_dir()
        file_path = os.path.join(upload_dir, filename)

        # Save the uploaded file
        logger.info(f"Saving uploaded file to: {file_path}")
        file.save(file_path)

        try:
            # Process the document
            markdown_content = mistral_service.process_document(file_path)
            
            # Return the results
            return jsonify({
                'markdown': markdown_content
            })
        finally:
            # Clean up the uploaded file
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Cleaned up uploaded file: {file_path}")
            except Exception as e:
                logger.error(f"Error cleaning up file: {e}")

    except Exception as e:
        logger.error(f"Error processing upload: {e}")
        return jsonify({'error': str(e)}), 500 