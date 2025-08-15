import pytesseract
from PIL import Image
from pdf2image import convert_from_path
import os
import tempfile

class OCRProcessor:
    def __init__(self):
        self.temp_dir = tempfile.gettempdir()
    
    def extract_text_from_pdf(self, pdf_path):
        """Extract text from PDF using OCR"""
        try:
            images = convert_from_path(pdf_path, dpi=300)
            
            full_text = ""
            for i, image in enumerate(images):
                text = pytesseract.image_to_string(image, lang='eng')
                full_text += f"\n--- Page {i+1} ---\n{text}"
            
            return full_text.strip()
        except Exception as e:
            raise Exception(f"OCR processing failed: {str(e)}")
    
    def extract_text_from_image(self, image_path):
        """Extract text from image file using OCR"""
        try:
            image = Image.open(image_path)
            text = pytesseract.image_to_string(image, lang='eng')
            return text.strip()
        except Exception as e:
            raise Exception(f"OCR processing failed: {str(e)}")
    
    def process_document(self, file_path):
        """Process document based on file type"""
        file_extension = os.path.splitext(file_path)[1].lower()
        
        if file_extension == '.pdf':
            return self.extract_text_from_pdf(file_path)
        elif file_extension in ['.png', '.jpg', '.jpeg', '.tiff', '.bmp']:
            return self.extract_text_from_image(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_extension}")