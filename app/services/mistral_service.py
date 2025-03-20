import os
import base64
from mistralai import Mistral
from pathlib import Path
import json

class MistralService:
    def __init__(self):
        self.settings_file = Path('instance/settings.json')
        self.api_key = self._load_api_key()
        self.client = None if not self.api_key else Mistral(api_key=self.api_key)
        
    def _load_api_key(self):
        """Load API key from settings file."""
        if self.settings_file.exists():
            with open(self.settings_file) as f:
                settings = json.load(f)
                return settings.get('mistral_api_key')
        return None
        
    def save_api_key(self, api_key):
        """Save API key to settings file."""
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)
        settings = {'mistral_api_key': api_key}
        with open(self.settings_file, 'w') as f:
            json.dump(settings, f)
        self.api_key = api_key
        self.client = Mistral(api_key=api_key)
        
    def process_document(self, file_path):
        """Process a document using Mistral's OCR API."""
        if not self.client:
            raise ValueError("API key not configured")
            
        # Encode file to base64
        with open(file_path, "rb") as file:
            base64_file = base64.b64encode(file.read()).decode('utf-8')
            
        # Get file extension
        file_type = Path(file_path).suffix.lower()[1:]
        mime_type = 'application/pdf' if file_type == 'pdf' else f'image/{file_type}'
        
        try:
            # Process with Mistral OCR
            response = self.client.ocr.process(
                model="mistral-ocr-latest",
                document={
                    "type": "image_url" if file_type != 'pdf' else "document_url",
                    "image_url": f"data:{mime_type};base64,{base64_file}"
                },
                include_image_base64=True
            )
            
            # Process the response to include images in markdown
            markdown_content = response.text
            if hasattr(response, 'images') and response.images:
                for img_id, img_data in response.images.items():
                    markdown_content = markdown_content.replace(
                        f"![{img_id}]({img_id})",
                        f"![{img_id}](data:image/png;base64,{img_data})"
                    )
            
            return markdown_content
            
        except Exception as e:
            raise Exception(f"Error processing document: {str(e)}")

# Create a singleton instance
mistral_service = MistralService() 