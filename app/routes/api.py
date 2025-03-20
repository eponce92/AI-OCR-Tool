from flask import Blueprint, jsonify, request
from app.services.mistral_service import mistral_service

api_bp = Blueprint('api', __name__)

@api_bp.route('/settings/api-key', methods=['GET'])
def get_api_key_status():
    """Check if API key is configured."""
    return jsonify({
        'has_api_key': bool(mistral_service.api_key)
    })

@api_bp.route('/settings/api-key', methods=['POST'])
def update_api_key():
    """Update the Mistral API key."""
    data = request.get_json()
    api_key = data.get('api_key')
    
    if not api_key:
        return jsonify({
            'success': False,
            'error': 'No API key provided'
        }), 400
        
    try:
        mistral_service.save_api_key(api_key)
        return jsonify({
            'success': True
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500 