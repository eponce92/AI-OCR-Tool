import os
import base64
from mistralai import Mistral
from pathlib import Path
import json
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MistralService:
    def __init__(self):
        self.settings_file = Path('instance/settings.json')
        self.api_key = self._load_api_key()
        self.client = None if not self.api_key else Mistral(api_key=self.api_key)
        self.supported_extensions = {'.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.bmp'}
        
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

    def _encode_image_base64(self, image_path):
        """Encode the image to base64."""
        try:
            with open(image_path, "rb") as image_file:
                image_data = image_file.read()
                if not image_data:
                    raise ValueError("Empty image file")
                return base64.b64encode(image_data).decode('utf-8')
        except Exception as e:
            logger.error(f"Error encoding image to base64: {str(e)}")
            raise Exception(f"Error encoding image to base64: {str(e)}")

    def _replace_images_in_markdown(self, markdown_str, images_dict):
        """Replace image placeholders in markdown with base64-encoded images."""
        for img_id, img_base64 in images_dict.items():
            if img_base64:  # Only replace if we have valid image data
                # Check if the image_base64 already has the data URL prefix
                if not img_base64.startswith('data:image/'):
                    # Guess the image type from the ID or default to jpeg
                    img_type = 'jpeg'
                    if '.' in img_id:
                        ext = img_id.split('.')[-1].lower()
                        if ext in ['png', 'jpg', 'jpeg', 'gif', 'webp']:
                            img_type = 'jpeg' if ext == 'jpg' else ext
                    img_base64 = f"data:image/{img_type};base64,{img_base64}"

                # Replace both URL and local file path patterns
                markdown_str = markdown_str.replace(
                    f"![{img_id}]({img_id})",
                    f"![{img_id}]({img_base64})"
                )
                # Also replace if it's trying to load from root URL
                markdown_str = markdown_str.replace(
                    f"![{img_id}](/{img_id})",
                    f"![{img_id}]({img_base64})"
                )
        return markdown_str
        
    def process_document(self, file_path):
        """Process a document using Mistral's OCR API."""
        if not self.client:
            logger.error("API key not configured")
            raise ValueError("API key not configured")
            
        # Check file extension
        file_ext = Path(file_path).suffix.lower()
        if file_ext not in self.supported_extensions:
            raise ValueError(f"Unsupported file type. Supported types are: {', '.join(self.supported_extensions)}")
            
        try:
            logger.info(f"Processing document: {file_path}")
            
            # Handle PDFs and images differently
            if file_ext == '.pdf':
                # For PDFs, use document_url approach
                with open(file_path, "rb") as file:
                    uploaded_file = self.client.files.upload(
                        file={
                            "file_name": Path(file_path).name,
                            "content": file,
                        },
                        purpose="ocr"
                    )
                
                logger.info("PDF uploaded successfully")
                
                try:
                    # Get a signed URL for the file
                    signed_url = self.client.files.get_signed_url(file_id=uploaded_file.id)
                    
                    # Process with Mistral OCR
                    response = self.client.ocr.process(
                        model="mistral-ocr-latest",
                        document={
                            "type": "document_url",
                            "document_url": signed_url.url
                        },
                        include_image_base64=True
                    )
                    
                    logger.info("Document processed successfully")
                finally:
                    # Clean up the uploaded file after processing
                    try:
                        self.client.files.delete(file_id=uploaded_file.id)
                        logger.info("Cleaned up uploaded file from Mistral")
                    except Exception as e:
                        logger.warning(f"Failed to delete uploaded file from Mistral: {e}")
                
            else:
                # For images, encode to base64 once and reuse
                base64_image = self._encode_image_base64(file_path)
                if not base64_image:
                    raise ValueError("Failed to encode image - empty file or invalid format")
                    
                image_type = file_ext[1:]  # Remove the dot from extension
                image_data_url = f"data:image/{image_type};base64,{base64_image}"
                
                logger.info("Processing image with OCR")
                # Process with Mistral OCR
                response = self.client.ocr.process(
                    model="mistral-ocr-latest",
                    document={
                        "type": "image_url",
                        "image_url": image_data_url
                    },
                    include_image_base64=True  # Make sure we get base64 images in response
                )
            
            logger.info("Document processed successfully")
            
            # Combine all pages' markdown content
            combined_markdown = []
            for page in response.pages:
                # Extract images from page
                image_data = {}
                if hasattr(page, 'images') and page.images:
                    for img in page.images:
                        if hasattr(img, 'image_base64') and img.image_base64:
                            # Store the raw base64 data - we'll add the data URL prefix in _replace_images_in_markdown
                            image_data[img.id] = img.image_base64
                
                # Replace image placeholders with actual images
                page_content = self._replace_images_in_markdown(page.markdown, image_data)
                combined_markdown.append(page_content)
            
            # Join all pages with a page separator
            return "\n\n---\n\n".join(combined_markdown)
            
        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            raise Exception(f"Error processing document: {str(e)}")

# Create a singleton instance
mistral_service = MistralService() 