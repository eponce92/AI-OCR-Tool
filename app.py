from flask import Flask, render_template, request, jsonify, send_file
import os
import requests
import base64
import json
import uuid
from werkzeug.utils import secure_filename
from docx import Document
import base64
import uuid
import os
import json
import requests
from langdetect import detect
from mistralai import Mistral

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'document' not in request.files:
        return jsonify({'error': 'No document part'}), 400
    
    file = request.files['document']
    
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    # Get API key from form data
    api_key = request.form.get('api_key')
    if not api_key:
        return jsonify({'error': 'Missing API key'}), 400
    
    # Check if we should include images in the response
    include_images = request.form.get('include_images') == 'true'
    
    if file:
        filename = secure_filename(file.filename)
        _, file_ext = os.path.splitext(filename)
        file_ext = file_ext.lower()
        
        # Check if file type is supported
        supported_types = {'.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.bmp'}
        if file_ext not in supported_types:
            return jsonify({'error': 'Unsupported file type. Please upload a PDF or image file (JPG, PNG, TIFF, BMP)'}), 400
        
        try:
            # Save the file
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            # Generate a unique file ID for preview
            file_id = str(uuid.uuid4())
            preview_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{file_id}_{filename}")
            
            # Create a copy for preview
            with open(file_path, 'rb') as src, open(preview_path, 'wb') as dst:
                dst.write(src.read())
            
            # Process with OCR
            result = process_with_mistral_ocr(file_path, filename, api_key, include_images)
            
            # Add preview file path to result
            result['preview_file'] = f"/preview/{file_id}_{filename}"
            
            # Clean up the original uploaded file, keep only the preview copy
            try:
                os.remove(file_path)
            except OSError:
                print(f"Warning: Could not remove temporary file {file_path}")
            
            return jsonify(result)
            
        except Exception as e:
            # Clean up files in case of error
            try:
                os.remove(file_path)
                os.remove(preview_path)
            except OSError:
                pass
            
            error_message = str(e)
            if "429" in error_message:
                error_message = "Rate limit exceeded. Please wait a moment before trying again."
            elif "401" in error_message:
                error_message = "Invalid API key. Please check your Mistral AI API key."
            elif "413" in error_message:
                error_message = "File is too large. Maximum file size is 16MB."
            
            return jsonify({'error': error_message}), 500
            
    return jsonify({'error': 'No file received'}), 400

@app.route('/preview/<path:filename>')
def serve_preview(filename):
    """Serve the uploaded document for preview"""
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))

@app.route('/batch-upload', methods=['POST'])
def batch_upload():
    if 'documents[]' not in request.files:
        return jsonify({'error': 'No documents provided'}), 400
    
    files = request.files.getlist('documents[]')
    api_key = request.form.get('api_key')
    
    if not api_key:
        return jsonify({'error': 'Missing API key'}), 400
    
    if not files or all(file.filename == '' for file in files):
        return jsonify({'error': 'No selected files'}), 400
    
    # Prepare batch request data
    batch_data = []
    temp_files = []
    
    try:
        for file in files:
            filename = secure_filename(file.filename)
            _, file_ext = os.path.splitext(filename)
            file_ext = file_ext.lower()
            
            # Check if file type is supported
            if file_ext not in {'.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.bmp'}:
                continue
            
            # Save file temporarily
            temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f"temp_{filename}")
            file.save(temp_path)
            temp_files.append(temp_path)
            
            # Create batch entry
            if file_ext == '.pdf':
                # For PDFs, upload to get signed URL
                upload_response = upload_file_for_ocr(temp_path, filename, api_key)
                if upload_response and 'url' in upload_response:
                    batch_data.append({
                        "custom_id": str(uuid.uuid4()),
                        "body": {
                            "document": {
                                "type": "document_url",
                                "document_url": upload_response['url'],
                                "document_name": filename
                            }
                        }
                    })
            else:
                # For images, use base64
                base64_image = encode_image(temp_path)
                if base64_image:
                    mime_type = get_mime_type(file_ext)
                    batch_data.append({
                        "custom_id": str(uuid.uuid4()),
                        "body": {
                            "document": {
                                "type": "image_url",
                                "image_url": f"data:{mime_type};base64,{base64_image}"
                            }
                        }
                    })
        
        if not batch_data:
            return jsonify({'error': 'No valid files to process'}), 400
        
        # Create batch job
        batch_file = create_batch_file(batch_data)
        batch_response = start_batch_job(batch_file, api_key)
        
        # Start polling for results
        return jsonify({
            'job_id': batch_response['id'],
            'status': 'processing',
            'total_files': len(batch_data)
        })
        
    except Exception as e:
        error_message = str(e)
        if "429" in error_message:
            error_message = "Rate limit exceeded. Please wait a moment before trying again."
        elif "401" in error_message:
            error_message = "Invalid API key. Please check your Mistral AI API key."
        
        return jsonify({'error': error_message}), 500
        
    finally:
        # Clean up temporary files
        for temp_file in temp_files:
            try:
                os.remove(temp_file)
            except OSError:
                pass

@app.route('/batch-status/<job_id>', methods=['GET'])
def batch_status(job_id):
    api_key = request.args.get('api_key')
    if not api_key:
        return jsonify({'error': 'Missing API key'}), 400
    
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        status_response = requests.get(
            f"https://api.mistral.ai/v1/batch/jobs/{job_id}",
            headers=headers
        )
        
        if status_response.status_code == 200:
            job_data = status_response.json()
            
            if job_data['status'] == 'completed':
                # Download and process results
                results = download_batch_results(job_data['output_file'], api_key)
                return jsonify({
                    'status': 'completed',
                    'results': results
                })
            else:
                return jsonify({
                    'status': job_data['status'],
                    'progress': {
                        'total': job_data['total_requests'],
                        'succeeded': job_data['succeeded_requests'],
                        'failed': job_data['failed_requests']
                    }
                })
        
        return jsonify({'error': 'Failed to get batch status'}), 500
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download/docx', methods=['POST'])
def download_docx():
    """Convert OCR text to DOCX format"""
    content = request.form.get('content')
    if not content:
        return jsonify({'error': 'No content provided'}), 400
    
    try:
        # Create a new Document
        doc = Document()
        
        # Add the content
        doc.add_paragraph(content)
        
        # Save the document to a temporary file
        temp_filename = f"temp_{uuid.uuid4()}.docx"
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], temp_filename)
        doc.save(temp_path)
        
        try:
            # Send the file
            response = send_file(
                temp_path,
                mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                as_attachment=True,
                download_name='ocr_results.docx'
            )
            
            # Delete the temporary file after sending
            @response.call_on_close
            def cleanup():
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
                    
            return response
            
        except Exception as e:
            # Clean up the temporary file if sending fails
            try:
                os.remove(temp_path)
            except OSError:
                pass
            raise e
            
    except Exception as e:
        return jsonify({'error': f'Failed to generate DOCX: {str(e)}'}), 500

def upload_file_for_ocr(file_path, filename, api_key):
    """Upload a file to Mistral API and get signed URL"""
    mime_type = get_mime_type(os.path.splitext(filename)[1].lower())
    
    with open(file_path, 'rb') as f:
        response = requests.post(
            "https://api.mistral.ai/v1/files",
            headers={"Authorization": f"Bearer {api_key}"},
            files={
                'file': (filename, f, mime_type),
                'purpose': (None, 'ocr')
            }
        )
    
    if response.status_code == 200:
        file_id = response.json().get('id')
        url_response = requests.get(
            f"https://api.mistral.ai/v1/files/{file_id}/url",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
        )
        
        if url_response.status_code == 200:
            return url_response.json()
    
    return None

def get_mime_type(extension):
    """Get MIME type from file extension"""
    mime_types = {
        '.pdf': 'application/pdf',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.tiff': 'image/tiff',
        '.bmp': 'image/bmp'
    }
    return mime_types.get(extension, 'application/octet-stream')

def create_batch_file(batch_data):
    """Create JSONL batch file"""
    batch_file = "batch_requests.jsonl"
    with open(batch_file, 'w') as f:
        for entry in batch_data:
            f.write(json.dumps(entry) + '\n')
    return batch_file

def start_batch_job(batch_file, api_key):
    """Start a batch processing job"""
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
    # Upload batch file
    with open(batch_file, 'rb') as f:
        upload_response = requests.post(
            "https://api.mistral.ai/v1/files",
            headers=headers,
            files={
                'file': ('batch.jsonl', f, 'application/json-lines'),
                'purpose': (None, 'batch')
            }
        )
    
    if upload_response.status_code != 200:
        raise Exception("Failed to upload batch file")
    
    file_id = upload_response.json()['id']
    
    # Create batch job
    job_response = requests.post(
        "https://api.mistral.ai/v1/batch/jobs",
        headers={**headers, "Content-Type": "application/json"},
        json={
            "input_files": [file_id],
            "model": "mistral-ocr-latest",
            "endpoint": "/v1/ocr"
        }
    )
    
    if job_response.status_code != 200:
        raise Exception("Failed to create batch job")
    
    return job_response.json()

def download_batch_results(file_id, api_key):
    """Download and process batch results"""
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
    # Get download URL
    url_response = requests.get(
        f"https://api.mistral.ai/v1/files/{file_id}/url",
        headers=headers
    )
    
    if url_response.status_code != 200:
        raise Exception("Failed to get results download URL")
    
    # Download results
    download_url = url_response.json()['url']
    results_response = requests.get(download_url)
    
    if results_response.status_code != 200:
        raise Exception("Failed to download results")
    
    # Process results
    results = []
    for line in results_response.text.splitlines():
        if line.strip():
            result = json.loads(line)
            if 'body' in result:
                processed_result = process_ocr_response(result['body'])
                results.append({
                    'custom_id': result.get('custom_id'),
                    'result': processed_result
                })
    
    return results

def encode_image(image_path):
    """Encode the image to base64."""
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except FileNotFoundError:
        print(f"Error: The file {image_path} was not found.")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def process_with_mistral_ocr(file_path, filename, api_key, include_images=False):
    """
    Process document with Mistral OCR API using the official SDK
    """
    # Get file extension and determine MIME type
    _, file_ext = os.path.splitext(filename)
    file_ext = file_ext.lower()
    
    mime_types = {
        '.pdf': 'application/pdf',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.tiff': 'image/tiff',
        '.bmp': 'image/bmp'
    }
    
    mime_type = mime_types.get(file_ext, 'application/octet-stream')
    is_pdf = file_ext == '.pdf'
    
    print(f"\n=== Starting OCR processing for {filename} ===")
    print(f"File type: {mime_type}")
    
    try:
        # Initialize Mistral client
        client = Mistral(api_key=api_key)
        
        if is_pdf:
            # For PDFs, use the file upload approach
            print("\n1. Uploading PDF to Mistral servers...")
            
            with open(file_path, "rb") as f:
                uploaded_file = client.files.upload(
                    file={
                        "file_name": filename,
                        "content": f,
                    },
                    purpose="ocr"
                )
            
            # Get signed URL for the uploaded file
            signed_url = client.files.get_signed_url(file_id=uploaded_file.id)
            
            # Make OCR request for PDF
            ocr_response = client.ocr.process(
                model="mistral-ocr-latest",
                document={
                    "type": "document_url",
                    "document_url": signed_url.url,
                    "document_name": filename
                },
                include_image_base64=include_images
            )
        else:
            # For images, use base64 encoding
            print("\n1. Encoding image as base64...")
            base64_image = encode_image(file_path)
            if not base64_image:
                raise Exception("Failed to encode image")
            
            # Make OCR request for image
            ocr_response = client.ocr.process(
                model="mistral-ocr-latest",
                document={
                    "type": "image_url",
                    "image_url": f"data:{mime_type};base64,{base64_image}"
                },
                include_image_base64=include_images
            )
        
        # Process the response
        processed_response = process_ocr_response(ocr_response)
        print(f"\nProcessed OCR Response: {json.dumps(processed_response)}")
        
        return processed_response
        
    except Exception as e:
        print(f"\nError during OCR processing: {str(e)}")
        raise

def serialize_dimensions(dimensions):
    """Convert OCRPageDimensions object to a serializable dictionary"""
    if dimensions is None:
        return {}
    return {
        "width": getattr(dimensions, "width", 0),
        "height": getattr(dimensions, "height", 0),
        "rotation": getattr(dimensions, "rotation", 0),
        "unit": getattr(dimensions, "unit", "pixel")
    }

def serialize_usage_info(usage_info):
    """Convert OCRUsageInfo object to a serializable dictionary"""
    if usage_info is None:
        return {}
    return {
        "total_tokens": getattr(usage_info, "total_tokens", 0),
        "completion_tokens": getattr(usage_info, "completion_tokens", 0),
        "prompt_tokens": getattr(usage_info, "prompt_tokens", 0)
    }

def process_ocr_response(response_data):
    """
    Process the OCR response to ensure a consistent structure with enhanced features
    """
    import re
    from langdetect import detect
    
    standardized_response = {
        "model": getattr(response_data, "model", "mistral-ocr"),
        "pages": [],
        "metadata": {
            "languages": [],
            "topics": [],
            "total_pages": 0
        },
        "usage_info": serialize_usage_info(getattr(response_data, "usage_info", None))
    }
    
    try:
        # Collect all text for language and topic detection
        all_text = []
        
        # Access pages directly from response object
        pages = getattr(response_data, "pages", [])
        if pages:
            standardized_response["metadata"]["total_pages"] = len(pages)
            
            for idx, page in enumerate(pages):
                # Initialize page data with serialized dimensions
                page_data = {
                    "page_num": idx,
                    "text": "",
                    "dimensions": serialize_dimensions(getattr(page, "dimensions", None)),
                    "images": [],
                    "markdown": ""  # Will contain text with image references
                }
                
                # Extract and process images
                images = getattr(page, "images", [])
                if images:
                    for img in images:
                        image_data = {
                            "id": getattr(img, "id", ""),
                            "coordinates": {
                                "top_left": [getattr(img, "top_left_x", 0), getattr(img, "top_left_y", 0)], 
                                "bottom_right": [getattr(img, "bottom_right_x", 0), getattr(img, "bottom_right_y", 0)]
                            },
                            "text": getattr(img, "text", ""),
                            "confidence": float(getattr(img, "confidence", 0)),
                            "type": getattr(img, "type", "unknown"),
                            "image_base64": getattr(img, "image_base64", "")
                        }
                        page_data["images"].append(image_data)
                        
                        # If image has associated text, add it to text content
                        if image_data["text"]:
                            if page_data["text"]:
                                page_data["text"] += "\n\n"
                            page_data["text"] += image_data["text"]
                            all_text.append(image_data["text"])
                
                # Extract text content
                text_content = getattr(page, "text", "") or getattr(page, "content", "")
                page_data["text"] = text_content
                
                # Generate markdown with image references
                md_content = getattr(page, "markdown", text_content)
                if page_data["images"]:
                    # Insert image references in markdown
                    for img in page_data["images"]:
                        if img["image_base64"]:
                            img_markdown = f"\n![{img['id']}](data:image/png;base64,{img['image_base64']})\n"
                            # Insert image reference near its associated text if exists
                            if img["text"] and img["text"] in md_content:
                                md_content = md_content.replace(img["text"], f"{img['text']}{img_markdown}")
                            else:
                                # Otherwise append at the end
                                md_content += img_markdown
                
                page_data["markdown"] = md_content
                all_text.append(text_content)
                
                standardized_response["pages"].append(page_data)
                
        # If no pages were processed but we have text directly
        elif hasattr(response_data, "text"):
            text = response_data.text
            all_text.append(text)
            standardized_response["pages"].append({
                "page_num": 0,
                "text": text,
                "markdown": text,
                "images": []
            })
            standardized_response["metadata"]["total_pages"] = 1
        
        # Process collected text for language and topic detection
        if all_text:
            combined_text = " ".join(all_text)
            
            # Detect language
            try:
                lang = detect(combined_text)
                standardized_response["metadata"]["languages"].append(lang)
            except:
                print("Language detection failed")
            
            # Basic topic detection based on keywords
            topics = detect_topics(combined_text)
            standardized_response["metadata"]["topics"] = topics
        
        # If we still have no content, set default message
        if not standardized_response["pages"]:
            standardized_response["pages"] = [{
                "page_num": 0,
                "text": "No text was extracted from this image. Please ensure the image contains readable text.",
                "markdown": "No text was extracted from this image. Please ensure the image contains readable text.",
                "images": []
            }]
            standardized_response["metadata"]["total_pages"] = 1
    
    except Exception as e:
        print(f"Error processing OCR response: {str(e)}")
        standardized_response["pages"] = [{
            "page_num": 0,
            "text": "Error processing OCR response. Please try again or contact support if the issue persists.",
            "markdown": "Error processing OCR response. Please try again or contact support if the issue persists.",
            "images": []
        }]
        standardized_response["error"] = str(e)
    
    return standardized_response

def detect_topics(text):
    """
    Basic topic detection based on keyword presence
    """
    topics = []
    
    # Define topic keywords
    topic_keywords = {
        "financial": ["invoice", "payment", "amount", "tax", "price", "cost"],
        "medical": ["patient", "doctor", "hospital", "medical", "health"],
        "legal": ["contract", "agreement", "law", "legal", "court"],
        "technical": ["software", "hardware", "system", "technical", "specification"],
        "educational": ["school", "university", "student", "education", "course"],
        "business": ["company", "business", "corporate", "meeting", "client"]
    }
    
    # Convert text to lowercase for case-insensitive matching
    text_lower = text.lower()
    
    # Check for each topic's keywords
    for topic, keywords in topic_keywords.items():
        if any(keyword in text_lower for keyword in keywords):
            topics.append(topic)
    
    return topics

def replace_images_in_markdown(markdown_str: str, images_dict: dict) -> str:
    """Replace image placeholders with base64 data URLs in markdown"""
    for img_name, base64_str in images_dict.items():
        markdown_str = markdown_str.replace(
            f"![{img_name}]({img_name})", 
            f"![{img_name}](data:image/png;base64,{base64_str})"
        )
    return markdown_str

def get_combined_markdown(ocr_response) -> str:
    """Combine markdown from all pages with image replacements"""
    markdowns = []
    for page in getattr(ocr_response, "pages", []):
        image_data = {}
        for img in getattr(page, "images", []):
            image_base64 = getattr(img, "image_base64", None)
            if image_base64:
                image_data[getattr(img, "id", "")] = image_base64
        markdowns.append(replace_images_in_markdown(
            getattr(page, "markdown", "") or getattr(page, "text", ""), 
            image_data
        ))
    return "\n\n".join(markdowns)

if __name__ == '__main__':
    app.run(debug=True)