from flask import Blueprint, render_template, request, jsonify, current_app
from werkzeug.utils import secure_filename
import os
from app.services.mistral_service import mistral_service
from pathlib import Path

main_bp = Blueprint('main', __name__)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

@main_bp.route('/')
def index():
    """Render the main page."""
    has_api_key = bool(mistral_service.api_key)
    return render_template('index.html', has_api_key=has_api_key)

@main_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    """Handle settings page and API key updates."""
    if request.method == 'POST':
        api_key = request.form.get('api_key')
        if api_key:
            mistral_service.save_api_key(api_key)
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'No API key provided'})
    
    return render_template('settings.html', 
                         has_api_key=bool(mistral_service.api_key))

@main_bp.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and OCR processing."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed'}), 400
        
    if not mistral_service.api_key:
        return jsonify({'error': 'API key not configured'}), 400
        
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        
        # Ensure upload directory exists
        Path(current_app.config['UPLOAD_FOLDER']).mkdir(parents=True, exist_ok=True)
        
        # Save the file
        file.save(filepath)
        
        # Process the file
        markdown_content = mistral_service.process_document(filepath)
        
        # Clean up the uploaded file
        os.remove(filepath)
        
        return jsonify({
            'success': True,
            'markdown': markdown_content
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500 