import pytesseract
from PIL import Image
from pdf2image import convert_from_path
import os
import tempfile
import PyPDF2
import re
from datetime import datetime
from typing import Tuple, Optional

class OCRProcessor:
    def __init__(self):
        self.temp_dir = tempfile.gettempdir()
    
    def extract_text_from_pdf(self, pdf_path) -> str:
        """Extract text from PDF - prefer native text, fallback to OCR"""
        try:
            # First try native text extraction
            native_text = self._extract_native_pdf_text(pdf_path)
            if native_text and len(native_text.strip()) > 100:
                return self._normalize_text(native_text)
            
            # Fallback to OCR if native text is insufficient
            images = convert_from_path(pdf_path, dpi=300)
            
            full_text = ""
            for i, image in enumerate(images):
                text = pytesseract.image_to_string(image, lang='eng', config='--psm 6')
                full_text += f"\n--- Page {i+1} ---\n{text}"
            
            return self._normalize_text(full_text.strip())
        except Exception as e:
            raise Exception(f"PDF text extraction failed: {str(e)}")
    
    def _extract_native_pdf_text(self, pdf_path: str) -> str:
        """Extract native text from PDF without OCR"""
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page_num, page in enumerate(pdf_reader.pages):
                    page_text = page.extract_text()
                    text += f"\n--- Page {page_num + 1} ---\n{page_text}"
                return text.strip()
        except Exception:
            return ""
    
    def extract_text_from_image(self, image_path) -> str:
        """Extract text from image file using OCR"""
        try:
            image = Image.open(image_path)
            text = pytesseract.image_to_string(image, lang='eng', config='--psm 6')
            return self._normalize_text(text.strip())
        except Exception as e:
            raise Exception(f"Image OCR processing failed: {str(e)}")
    
    def process_document(self, file_path) -> str:
        """Process document based on file type"""
        file_extension = os.path.splitext(file_path)[1].lower()
        
        if file_extension == '.pdf':
            return self.extract_text_from_pdf(file_path)
        elif file_extension in ['.png', '.jpg', '.jpeg', '.tiff', '.bmp']:
            return self.extract_text_from_image(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_extension}")
    
    def _normalize_text(self, text: str) -> str:
        """Normalize extracted text for consistent processing"""
        if not text:
            return ""
        
        # Normalize currency symbols and amounts
        text = self._normalize_currency(text)
        
        # Normalize dates
        text = self._normalize_dates(text)
        
        # Normalize units
        text = self._normalize_units(text)
        
        # Clean up whitespace and formatting
        text = re.sub(r'\s+', ' ', text)  # Multiple whitespace to single space
        text = re.sub(r'\n\s*\n', '\n', text)  # Multiple newlines to single
        
        return text.strip()
    
    def _normalize_currency(self, text: str) -> str:
        """Normalize currency formats"""
        # Convert various currency formats to standard $X,XXX.XX
        # Handle formats like: $1,234.56, USD 1234.56, 1,234.56 USD, etc.
        
        # Pattern for currency amounts
        currency_patterns = [
            r'USD\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # USD 1,234.56
            r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*USD',  # 1,234.56 USD
            r'\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',   # $ 1,234.56
        ]
        
        for pattern in currency_patterns:
            text = re.sub(pattern, r'$\1', text)
        
        return text
    
    def _normalize_dates(self, text: str) -> str:
        """Normalize date formats to ISO format where possible"""
        # Common date patterns to normalize
        date_patterns = [
            (r'(\d{1,2})/(\d{1,2})/(\d{4})', r'\3-\2-\1'),  # MM/DD/YYYY to YYYY-MM-DD
            (r'(\d{1,2})-(\d{1,2})-(\d{4})', r'\3-\2-\1'),  # MM-DD-YYYY to YYYY-MM-DD
            (r'(\d{4})/(\d{1,2})/(\d{1,2})', r'\1-\2-\3'),  # YYYY/MM/DD to YYYY-MM-DD
        ]
        
        for pattern, replacement in date_patterns:
            text = re.sub(pattern, replacement, text)
        
        return text
    
    def _normalize_units(self, text: str) -> str:
        """Normalize unit measurements"""
        # Standardize common units
        unit_replacements = {
            r'\bea\b': 'each',
            r'\bpcs?\b': 'pieces',
            r'\bhr\b': 'hour',
            r'\bhrs\b': 'hours',
            r'\bmo\b': 'month',
            r'\bmos\b': 'months',
            r'\byr\b': 'year',
            r'\byrs\b': 'years',
            r'\blbs?\b': 'pounds',
            r'\bft\b': 'feet',
            r'\bin\b': 'inches',
        }
        
        for pattern, replacement in unit_replacements.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
        return text