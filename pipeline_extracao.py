#!/usr/bin/env python3
"""
PDF to Text & Image Analysis Pipeline with OpenAI

This script extracts text and images from PDF documents, sends them for AI analysis,
and saves the results as structured JSON files. It processes documents in chunks to
handle large files efficiently and includes comprehensive error handling and logging.

Author: Pipeline Extraction Team
Version: 2.0
"""

# Standard library imports
import base64
import concurrent.futures
import io
import json
import logging
import os
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any

# Third-party imports
import fitz  # PyMuPDF
import tiktoken
from dotenv import load_dotenv
from openai import APIError, OpenAI, RateLimitError
from pdf2image import convert_from_path
from tqdm import tqdm

# Local imports
from prompts import analysis_prompt, pproc_prompt

# -------------------------------------------------------------------
# Configuration and Setup
# -------------------------------------------------------------------

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pipeline_extraction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration class
class Config:
    """Configuration management for the extraction pipeline."""
    
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        self.client = OpenAI(api_key=self.api_key)
        
        # Model configurations
        self.analysis_model_default = "gpt-4o-mini"
        self.analysis_model_large = "gpt-4o"
        self.pproc_model = "gpt-4o-mini"
        
        # Processing parameters
        self.chunk_size = 10
        self.max_workers = 3
        self.max_retries = 3
        self.backoff_base = 5
        self.image_dpi = 200  # Optimized DPI for performance
        self.max_tokens_per_request = 1000
        
        # Directory paths
        self.base_dir = Path("../assets")
        self.json_results_dir = self.base_dir / "json_results"
        self.pdfs_dir = self.base_dir / "pdfs"
        
        # Subdirectories
        self.raw_dir = self.json_results_dir / "raw"
        self.bronze_dir = self.json_results_dir / "bronze"
        self.silver_dir = self.json_results_dir / "silver"
        self.gold_dir = self.json_results_dir / "gold"
        self.pdfs_raw_dir = self.pdfs_dir / "brutos"
        self.pdfs_processed_dir = self.pdfs_dir / "parcionados"

# Global configuration instance
config = Config()
logger.info("Configuration loaded successfully")

# -------------------------------------------------------------------
# Utility Functions
# -------------------------------------------------------------------

def create_directories() -> None:
    """Create necessary directories for the pipeline."""
    directories = [
        config.raw_dir,
        config.bronze_dir,
        config.silver_dir,
        config.gold_dir,
        config.pdfs_raw_dir,
        config.pdfs_processed_dir,
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        logger.info(f"Directory verified/created: {directory}")




def count_tokens(model: str, text: str) -> int:
    """Count tokens in text for a specific model."""
    try:
        enc = tiktoken.encoding_for_model(model)
        return len(enc.encode(text))
    except Exception as e:
        logger.warning(f"Failed to count tokens for model {model}: {e}")
        return len(text.split()) * 2  # Rough estimation


def estimate_total_tokens(model: str, texts: List[str], num_images: int) -> int:
    """Estimate total tokens considering base prompt once and applying safety margin."""
    try:
        total = count_tokens(model, analysis_prompt)  # Base prompt once
        for text in texts:
            total += count_tokens(model, text)  # Page text
            total += 85  # Average cost per image
        return int(total * 1.2)  # 20% safety margin
    except Exception as e:
        logger.error(f"Error estimating tokens: {e}")
        return 100000  # Conservative fallback


def check_poppler_availability() -> bool:
    """Check if Poppler is available in the system."""
    try:
        from pdf2image import convert_from_path
        # Try to convert a dummy path to test Poppler availability
        convert_from_path("dummy.pdf", first_page=1, last_page=1)
        return True
    except Exception as e:
        if "poppler" in str(e).lower() or "page count" in str(e).lower():
            return False
        return True  # Other errors might not be Poppler-related

def convert_pdf_to_images_pymupdf(path: Union[str, Path], dpi: int = 200) -> List[Any]:
    """Convert PDF to images using PyMuPDF as fallback when Poppler is not available."""
    try:
        import fitz
        from PIL import Image
        import io
        
        logger.info(f"Converting PDF to images using PyMuPDF: {path}")
        
        doc = fitz.open(str(path))
        images = []
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            # Calculate zoom factor based on DPI (72 is default PDF DPI)
            zoom = dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            
            # Convert to PIL Image
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            images.append(img)
        
        doc.close()
        logger.info(f"Successfully converted {len(images)} pages using PyMuPDF")
        return images
        
    except Exception as e:
        logger.error(f"Failed to convert PDF using PyMuPDF: {e}")
        raise

def convert_doc_to_images(path: Union[str, Path], dpi: int = 200) -> List[Any]:
    """Convert PDF document to images with Poppler detection and PyMuPDF fallback."""
    try:
        logger.info(f"Converting PDF to images: {path}")
        
        # First try with pdf2image (Poppler)
        if check_poppler_availability():
            logger.info("Using pdf2image with Poppler")
            return convert_from_path(
                str(path),
                dpi=dpi,
                fmt='PNG',
                thread_count=2,  # Limit threads to avoid memory issues
                use_pdftocairo=True  # Use poppler-utils for better performance
            )
        else:
            logger.warning("Poppler not available, falling back to PyMuPDF")
            return convert_pdf_to_images_pymupdf(path, dpi)
            
    except Exception as e:
        error_msg = str(e).lower()
        if "poppler" in error_msg or "page count" in error_msg:
            logger.warning("Poppler error detected, trying PyMuPDF fallback")
            try:
                return convert_pdf_to_images_pymupdf(path, dpi)
            except Exception as fallback_error:
                logger.error(f"Both pdf2image and PyMuPDF failed: {fallback_error}")
                raise RuntimeError(
                    f"Failed to convert PDF to images. Poppler error: {e}. "
                    f"PyMuPDF fallback also failed: {fallback_error}. "
                    f"Please install Poppler or check your PDF file."
                )
        else:
            logger.error(f"Failed to convert PDF to images: {e}")
            raise


def get_img_uri(img: Any) -> str:
    """Convert PIL image to base64 data URI."""
    try:
        png_buffer = io.BytesIO()
        img.save(png_buffer, format="PNG")
        png_buffer.seek(0)
        base64_png = base64.b64encode(png_buffer.read()).decode("utf-8")
        return f"data:image/png;base64,{base64_png}"
    except Exception as e:
        logger.error(f"Failed to convert image to URI: {e}")
        raise


def extract_text_by_page(path: Union[str, Path]) -> List[str]:
    """Extract text from PDF document page by page."""
    try:
        logger.info(f"Extracting text from PDF: {path}")
        with fitz.open(str(path)) as doc:
            return [page.get_text("text") for page in doc]
    except Exception as e:
        logger.error(f"Failed to extract text from PDF: {e}")
        raise


def load_safe_json(raw_str: str) -> Dict[str, Any]:
    """Validate and fix malformed JSON returned by AI."""
    try:
        return json.loads(raw_str)
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON detected: {e}")
        cleaned = raw_str.strip().replace("```json", "").replace("```", "")
        try:
            return json.loads(cleaned)
        except Exception as e2:
            logger.error(f"Failed to fix JSON: {e2}")
            return {"error": "invalid_json", "raw": cleaned}


def split_list(lst: List[Any], n: int):
    """Split list into chunks of size n."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def validate_file_path(file_path: Union[str, Path]) -> Path:
    """Validate that file path exists and is readable."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not path.is_file():
        raise ValueError(f"Path is not a file: {path}")
    if not os.access(path, os.R_OK):
        raise PermissionError(f"File is not readable: {path}")
    return path


def cleanup_temp_files() -> None:
    """Clean up any temporary files created during processing."""
    try:
        # This could be expanded to clean up any temporary files
        logger.debug("Cleanup completed")
    except Exception as e:
        logger.warning(f"Error during cleanup: {e}")


# -------------------------------------------------------------------
# Processing Functions
# -------------------------------------------------------------------

def safe_pproc(pproc_prompt: str, path: Union[str, Path], json_str: str, retries: int = None) -> str:
    """Safely process with retry logic for API errors."""
    if retries is None:
        retries = config.max_retries
    
    backoff = config.backoff_base
    
    for attempt in range(retries):
        try:
            return pproc(pproc_prompt, path, json_str)
        except (RateLimitError, APIError) as e:
            wait = backoff * (2 ** attempt) + random.uniform(0, 2)
            logger.warning(f"API error in pproc: {e}. Retrying in {wait:.1f}s... (attempt {attempt + 1}/{retries})")
            time.sleep(wait)
        except Exception as e:
            logger.error(f"Unexpected error in pproc: {e}")
            raise
    
    raise RuntimeError(f"pproc failed after {retries} attempts")

def pproc(pproc_prompt: str, path: Union[str, Path], json_str: str) -> str:
    """Process document with OpenAI API for structured JSON extraction."""
    logger.info(f"Processing file: {path}")
    
    try:
        with open(path, "rb") as file:
            uploaded_file = config.client.files.create(
                file=file,
                purpose="user_data"
            )

        json_sys_prompt = (
            f"{pproc_prompt}\n\n"
            f"Here is the extracted content so far. Do not summarize. "
            f"Expand and reorganize into the structured JSON format exactly as shown. "
            f"Preserve all details, conditions, and states: {json_str}"
        )

        response = config.client.responses.create(
            model=config.pproc_model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_file", "file_id": uploaded_file.id},
                        {"type": "input_text", "text": json_sys_prompt},
                    ],
                }
            ],
        )
        
        # Clean up the uploaded file
        config.client.files.delete(uploaded_file.id)
        
        if config.pproc_model == "gpt-5-mini":
            return response.output_text.replace("```json", "").replace("```", "")
        else:
            return str(response.output[0].content[0].text).replace("```json", "").replace("```", "")
            
    except Exception as e:
        logger.error(f"Error in pproc for file {path}: {e}")
        raise


def analyze_doc_image(img: Any, text: str, model: str = None) -> str:
    """Analyze document image with text using OpenAI vision model."""
    if model is None:
        model = config.analysis_model_default
    
    try:
        img_uri = get_img_uri(img)
        return analyze_image(img_uri, text, model)
    except Exception as e:
        logger.error(f"Error analyzing document image: {e}")
        raise


def analyze_image(data_uri: str, text: str, model: str = None) -> str:
    """Analyze image + text using OpenAI vision model (no automatic retries)."""
    if model is None:
        model = config.analysis_model_default
    
    try:
        response = config.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": analysis_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_uri}},
                        {"type": "text", "text": text},
                    ],
                },
            ],
            max_tokens=config.max_tokens_per_request,
            temperature=0,
            top_p=0.1,
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error analyzing image: {e}")
        raise

# -------------------------------------------------------------------
# Main Pipeline Functions
# -------------------------------------------------------------------

def get_pdf_files(directory_path: Union[str, Path], selected_file: Optional[str] = None) -> List[str]:
    """Get list of PDF files from directory, optionally filtering by selected file."""
    directory_path = Path(directory_path)
    
    if not directory_path.is_dir():
        raise FileNotFoundError(f"Directory not found: {directory_path}")
    
    all_items = os.listdir(directory_path)
    pdf_files = [
        item for item in all_items 
        if (directory_path / item).is_file() and item.lower().endswith(".pdf")
    ]
    
    if selected_file:
        if selected_file not in pdf_files:
            raise FileNotFoundError(f"Selected file '{selected_file}' not found in {directory_path}")
        pdf_files = [selected_file]
    else:
        logger.info("No file selected — processing all PDFs in directory.")
    
    logger.info(f"Found {len(pdf_files)} PDF files to process")
    return pdf_files


def process_document_chunk(chunk: List[Tuple[int, Any]], texts: List[str], model: str) -> List[str]:
    """Process a chunk of document pages with parallel processing."""
    pages_description = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=config.max_workers) as executor:
        futures = [
            executor.submit(analyze_doc_image, img, texts[idx], model) 
            for idx, img in chunk
        ]
        
        with tqdm(total=len(chunk), desc="Processing pages") as pbar:
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    pages_description.append(result)
                except Exception as e:
                    logger.error(f"Error processing page: {e}")
                    pages_description.append(f"Error processing page: {str(e)}")
                finally:
                    pbar.update(1)
    
    return pages_description


def save_raw_results(docs: List[Dict[str, Any]], filename: str, timestamp: str) -> Path:
    """Save raw analysis results to JSON file."""
    raw_path = config.raw_dir / f"raw_{filename}_{timestamp}.json"
    
    try:
        with open(raw_path, "w", encoding="utf-8") as file:
            json.dump(docs, file, ensure_ascii=False, indent=2)
        
        logger.info(f"Raw results saved: {raw_path}")
        return raw_path
    except Exception as e:
        logger.error(f"Failed to save raw results: {e}")
        raise


def save_bronze_results(json_data: Dict[str, Any], filename: str, timestamp: str) -> Path:
    """Save processed bronze results to JSON file."""
    bronze_path = config.bronze_dir / f"bronze_{filename}_{timestamp}.json"
    
    try:
        with open(bronze_path, "w", encoding="utf-8") as file:
            json.dump(json_data, file, ensure_ascii=False, indent=2)
        
        logger.info(f"Bronze results saved: {bronze_path}")
        return bronze_path
    except Exception as e:
        logger.error(f"Failed to save bronze results: {e}")
        raise


def process_single_document(file_path: Union[str, Path], filename: str, timestamp: str) -> Dict[str, Any]:
    """Process a single PDF document through the complete pipeline."""
    logger.info(f"Processing document: {filename}")
    
    try:
        # Validate file path
        validated_path = validate_file_path(file_path)
        
        # Convert PDF to images and extract text
        imgs = convert_doc_to_images(validated_path, config.image_dpi)
        texts = extract_text_by_page(validated_path)
        
        if len(imgs) != len(texts):
            logger.warning(f"Mismatch between image count ({len(imgs)}) and text count ({len(texts)})")
        
        # Choose model based on content size
        chosen_model = config.analysis_model_large
        logger.info(f"Using model: {chosen_model}")
        
        # Process in chunks
        pages_description = []
        for chunk in split_list(list(enumerate(imgs)), config.chunk_size):
            chunk_results = process_document_chunk(chunk, texts, chosen_model)
            pages_description.extend(chunk_results)
        
        # Create document result
        doc = {
            "filename": filename,
            "pages_description": pages_description,
            "processing_timestamp": timestamp,
            "total_pages": len(imgs)
        }
        
        return doc
        
    except Exception as e:
        logger.error(f"Error processing document {filename}: {e}")
        raise

def pipeline(path_parcionados: Union[str, Path], selected_file: Optional[str] = None, chunk_size: int = None) -> None:
    """
    Main pipeline function to process PDF documents.
    
    Args:
        path_parcionados: Path to directory containing PDF files
        selected_file: Optional specific file to process
        chunk_size: Optional chunk size for processing (defaults to config)
    """
    # Update chunk size if provided
    if chunk_size is not None:
        config.chunk_size = chunk_size
    
    # Initialize directories
    create_directories()
    
    # Get list of PDF files to process
    files = get_pdf_files(path_parcionados, selected_file)
    
    if not files:
        logger.warning("No PDF files found to process")
        return
    
    timestamp = datetime.now().strftime(r"%Y%m%dT%H%M%S")
    
    # Process each file
    for filename in files:
        try:
            file_path = Path(path_parcionados) / filename
            base_filename = filename.rsplit(".", 1)[0]
            
            logger.info(f"Starting processing of: {filename}")
            
            # Process the document
            doc = process_single_document(file_path, filename, timestamp)
            
            # Save raw results
            raw_path = save_raw_results([doc], base_filename, timestamp)
            
            # Process with pproc for structured output
            try:
                with open(raw_path, "r", encoding="utf-8") as file:
                    json_content = file.read()
                
                logger.info(f"Processing with pproc: {filename}")
                processed_json = safe_pproc(pproc_prompt, file_path, json_content)
                final_json = load_safe_json(processed_json)
                
                # Save bronze results
                save_bronze_results(final_json, base_filename, timestamp)
                
            except Exception as e:
                logger.error(f"Error in pproc processing for {filename}: {e}")
                # Continue with next file even if pproc fails
                
        except Exception as e:
            logger.error(f"Failed to process {filename}: {e}")
            # Continue with next file
            
    logger.info("Pipeline processing completed")


def diagnose_system() -> None:
    """Diagnose system dependencies and provide helpful information."""
    logger.info("=== System Diagnosis ===")
    
    # Check Poppler availability
    poppler_available = check_poppler_availability()
    if poppler_available:
        logger.info("✅ Poppler is available - pdf2image will work optimally")
    else:
        logger.warning("⚠️ Poppler not available - will use PyMuPDF fallback")
        logger.info("To install Poppler:")
        logger.info("  Windows: Download from https://github.com/oschwartz10612/poppler-windows/releases/")
        logger.info("  macOS: brew install poppler")
        logger.info("  Linux: sudo apt-get install poppler-utils")
    
    # Check PyMuPDF
    try:
        import fitz
        logger.info("✅ PyMuPDF is available - fallback conversion will work")
    except ImportError:
        logger.error("❌ PyMuPDF not available - install with: pip install pymupdf")
    
    # Check OpenAI API key
    if config.api_key:
        logger.info("✅ OpenAI API key is configured")
    else:
        logger.error("❌ OpenAI API key not found - set OPENAI_API_KEY environment variable")
    
    logger.info("=== End Diagnosis ===")

def main() -> None:
    """Main entry point for the pipeline."""
    try:
        # Run system diagnosis
        diagnose_system()
        
        # Example usage - modify paths as needed
        pdf_directory = "../assets/pdfs/parcionados"
        
        logger.info("Starting PDF extraction pipeline")
        
        # Process all PDFs in directory
        pipeline(pdf_directory)
        
        # Or process a specific file:
        # pipeline(pdf_directory, selected_file="example.pdf")
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        raise
    finally:
        cleanup_temp_files()


if __name__ == "__main__":
    main()
