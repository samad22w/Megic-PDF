# (Your full code here...)
import gradio as gr
import gradio as gr
import fitz  # PyMuPDF
from pdf2image import convert_from_path
import pytesseract
from PIL import Image
import tempfile
import os
import html
import re
import io
from docx import Document # Import Document class
# from gradio import utils # Removed since gr.utils.strip_html doesn't exist

# Helper function to manually strip HTML tags
def strip_html_manual(text):
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)


# -------- Extract all PDF text --------
def extract_pdf_all(pdf_file):
    if pdf_file is None:
        return "Please upload a PDF file."
    pdf_path = pdf_file.name
    try:
        doc = fitz.open(pdf_path)
        extracted_text = []
        pages_with_no_text = []

        for i, page in enumerate(doc):
            text = page.get_text("text")
            if text.strip():
                extracted_text.append(f"--- Page {i+1} ---\n{text}")
            else:
                pages_with_no_text.append(i)

        if pages_with_no_text:
            # Use a temporary directory for images from pdf2image
            with tempfile.TemporaryDirectory() as temp_dir:
                try:
                    images = convert_from_path(pdf_path, dpi=300, output_folder=temp_dir)
                    for idx in pages_with_no_text: # Corrected: should be pages_with_no_text
                        if idx < len(images):
                            img = images[idx]
                            text = pytesseract.image_to_string(img)
                            extracted_text.append(f"--- Page {idx+1} (OCR) ---\n{text}")
                        else:
                             extracted_text.append(f"--- Page {idx+1} (OCR Failed - Image not found) ---")
                except Exception as e:
                     print(f"Error during pdf2image conversion or OCR on no-text pages: {e}")
                     extracted_text.append("--- Error during OCR on no-text pages ---")


        return "\n\n".join(extracted_text)
    except Exception as e:
        return f"An error occurred during extraction: {e}"


# -------- Extract text from specific page --------
def extract_pdf_page(pdf_file, page_num):
    if pdf_file is None:
        return "Please upload a PDF file."
    if not isinstance(page_num, (int, float)) or page_num < 1:
         return "Invalid page number. Please enter a positive integer."

    pdf_path = pdf_file.name
    try:
        doc = fitz.open(pdf_path)
        page_index = int(page_num) - 1

        if page_index < 0 or page_index >= len(doc):
            return f"❌ Invalid page number. PDF has {len(doc)} pages."

        page = doc[page_index]
        text = page.get_text("text")

        # Also attempt OCR for images on the page
        img_text = []
        for img_index, img_info in enumerate(page.get_images(full=True)):
             xref = img_info[0]
             try:
                 base_image = doc.extract_image(xref)
                 image_bytes = base_image["image"]
                 img_pil = Image.open(io.BytesIO(image_bytes))
                 if img_pil.mode != "RGB":
                     img_pil = img_pil.convert("RGB")
                 img_text.append(pytesseract.image_to_string(img_pil))
             except Exception as e:
                 print(f"Could not process image {img_index} on page {page_num}: {e}")
                 continue

        combined_text = text.strip()
        if img_text:
            combined_text += "\n" + "\n".join(img_text).strip()
        if not combined_text:
             combined_text = "No text found on this page (either text layer or images)."

        return f"--- Page {int(page_num)} ---\n{combined_text}"
    except Exception as e:
        return f"An error occurred during page extraction: {e}"


# -------- Search inside PDF (with highlighting) --------
def search_pdf(pdf_file, query):
    if pdf_file is None:
        return "Please upload a PDF file."
    if not query or not query.strip():
        return "Please enter text to search for."

    pdf_path = pdf_file.name
    try:
        doc = fitz.open(pdf_path)
        results_html = ""
        found_matches = False

        for i, page in enumerate(doc):
            text = page.get_text("text")
            if query.lower() in text.lower():
                found_matches = True
                safe_text = html.escape(text).replace("\n", "<br>")
                # Use re.sub for case-insensitive replacement and to handle multiple occurrences
                highlighted_text = re.sub(f'({re.escape(query)})',
                                          r'<span style="background-color: yellow;">\1</span>',
                                          safe_text, flags=re.IGNORECASE)
                results_html += f"<div style='margin-bottom: 15px;'><b>✅ Found on Page {i+1}:</b><br>{highlighted_text}</div>"

        if not found_matches:
             # Fallback to OCR search if not found in text layer
            all_text_ocr = extract_pdf_all(pdf_file) # This will use OCR
            if query.lower() in all_text_ocr.lower():
                 return "✅ Found in OCR text (may be in images or scanned pages)."
            else:
                return "❌ Not found in PDF (text layer or OCR)."


        return results_html
    except Exception as e:
        return f"An error occurred during search: {e}"


# -------- Extract text from Image (from PDF page) --------
def extract_image_text_from_pdf_page(pdf_file, page_num):
     if pdf_file is None:
        return "Please upload a PDF file."
     if not isinstance(page_num, (int, float)) or page_num < 1:
         return "Invalid page number. Please enter a positive integer."

     pdf_path = pdf_file.name
     try:
        doc = fitz.open(pdf_path)
        page_index = int(page_num) - 1

        if page_index < 0 or page_index >= len(doc):
            return f"❌ Invalid page number. PDF has {len(doc)} pages."

        page = doc[page_index]

        img_text = []
        for img_index, img_info in enumerate(page.get_images(full=True)):
             xref = img_info[0]
             try:
                 base_image = doc.extract_image(xref)
                 image_bytes = base_image["image"]
                 img_pil = Image.open(io.BytesIO(image_bytes))
                 if img_pil.mode != "RGB":
                     img_pil = img_pil.convert("RGB")
                 img_text.append(pytesseract.image_to_string(img_pil))
             except Exception as e:
                 print(f"Could not process image {img_index} on page {page_num}: {e}")
                 continue

        if not img_text:
            return f"No images found on Page {int(page_num)} with extractable text."

        return "\n\n".join(img_text)

     except Exception as e:
         return f"An error occurred during image text extraction from page: {e}"


# -------- Save text to file (for download) --------
def save_text_as_file(text, format):
    print(f"save_text_as_file called with text (first 100 chars): {text[:100]} and format: {format}")
    if not text or "Please upload a PDF file." in text or "An error occurred" in text or "❌" in text or "No images found" in text:
        print("save_text_as_file: No valid content to save.")
        return None # Don't provide a download link if there's no valid content

    try:
        # Remove HTML tags if the output is HTML (like from search results with highlighting)
        # Use manual HTML stripping
        cleaned_text = strip_html_manual(text) if "<div" in text else text
        print(f"save_text_as_file: Cleaned text (first 100 chars): {cleaned_text[:100]}")

        if format == "DOCX":
            document = Document()
            # Add lines as paragraphs to preserve some structure
            for line in cleaned_text.splitlines():
                document.add_paragraph(line)
            tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".docx", mode='wb')
            document.save(tmp_file)
            tmp_file.close()
            print(f"save_text_as_file: Saved DOCX file to {tmp_file.name}")
            return tmp_file.name
        else: # Default to TXT
            tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode='w', encoding='utf-8')
            tmp_file.write(cleaned_text)
            tmp_file.close()
            print(f"save_text_as_file: Saved TXT file to {tmp_file.name}")
            return tmp_file.name

    except Exception as e:
        print(f"Error creating download file: {e}")
        return None

# -------- Clear function --------
def clear_all():
    return None, "", 1, "", None, "TXT"


# -------- Gradio UI with Styling --------
custom_css = """
body {
    background: linear-gradient(135deg, #4facfe, #8e44ad);
    font-family: 'Poppins', sans-serif;
}
.gradio-container {
    max-width: 900px !important;
    margin: auto;
    border-radius: 25px; /* Increased border radius for rounder corners */
    box-shadow: 0px 5px 20px rgba(0,0,0,0.2);
    padding: 20px;
    /* Set background to transparent */
    background-color: rgba(255, 255, 255, 0.8); /* Semi-transparent white */
    box-shadow: 0px 5px 20px rgba(0,0,0,0.1); /* Keep a subtle shadow */
}
button {
    border-radius: 12px !important;
    font-weight: bold !important;
    font-size: 15px !important;
    padding: 10px 20px !important;
    color: white !important;
    transition: transform 0.2s ease-in-out; /* Add transition for smooth zoom */
}
button:hover {
    transform: scale(1.05); /* Zoom in slightly on hover */
}
/* Custom button colors - adjust as needed */
#btn-extract-all { background: #27ae60 !important; } /* Green */
#btn-extract-page { background: #2980b9 !important; } /* Blue */
#btn-search { background: #8e44ad !important; }     /* Purple */
#btn-extract-img { background: #e67e22 !important; } /* Orange */
#btn-clear { background: #f0ad4e !important; } /* Yellowish-orange for Clear */

/* Styled title with gradient color */
.gradio-markdown h2 {
    text-align: center;
    font-size: 28px;
    font-weight: bold;
    margin-bottom: 20px;
    background: linear-gradient(45deg, #FF5733, #FFC300, #DAF7A6); /* 3-color gradient */
    -webkit-background-clip: text; /* Apply gradient to text */
    -webkit-text-fill-color: transparent; /* Make text transparent to show gradient */
    text-shadow: 2px 2px 4px rgba(0,0,0,0.3); /* Keep text shadow for readability */
}
"""

with gr.Blocks(css=custom_css) as demo:
    gr.Markdown("<h2 style='text-align:center;'> AI PDF & Image Text Extractor</h2>") # Styled title

    with gr.Row():
        with gr.Column(scale=1):
            pdf_input = gr.File(label="📂 Upload PDF", file_types=[".pdf"], type="filepath")
            page_num_input = gr.Number(label="📝 Page Number (for specific page/image)", value=1, precision=0)
            query_input = gr.Textbox(label="🔎 Enter word/phrase to search (optional)")
            # Add the download format radio button
            download_format_input = gr.Radio(
                label="💾 Download Format",
                choices=["TXT", "DOCX"],
                value="TXT",
                interactive=True
            )

            gr.Markdown("---") # Separator

            # Buttons for different actions
            btn_extract_all = gr.Button("📥 Extract All PDF Text", elem_id="btn-extract-all")
            btn_extract_page = gr.Button("📑 Extract Specific Page Text", elem_id="btn-extract-page")
            btn_extract_img = gr.Button("🖼️ Extract Image Text from Page", elem_id="btn-extract-img")
            btn_search = gr.Button("🔍 Search in PDF", elem_id="btn-search")

            gr.Markdown("---") # Separator
            # Removed the download button as requested


        with gr.Column(scale=2):
            output_text = gr.HTML(label="📄 Extracted / Search Result")
            # Kept the download_file component which becomes interactive when a file is ready
            download_file = gr.File(label="Download File", interactive=False)
            btn_clear = gr.Button("🧹 Clear All", elem_id="btn-clear") # Clear button


    # Define click actions
    btn_extract_all.click(extract_pdf_all, inputs=pdf_input, outputs=output_text)
    btn_extract_page.click(extract_pdf_page, inputs=[pdf_input, page_num_input], outputs=output_text)
    btn_search.click(search_pdf, inputs=[pdf_input, query_input], outputs=output_text)
    btn_extract_img.click(extract_image_text_from_pdf_page, inputs=[pdf_input, page_num_input], outputs=output_text)

    # Use the change event of the output_text to trigger download file creation
    # This links the output text and the download format to the save function,
    # and the result (file path) updates the download_file component.
    output_text.change(save_text_as_file, inputs=[output_text, download_format_input], outputs=download_file)


    # Clear button action
    btn_clear.click(clear_all, inputs=[], outputs=[pdf_input, output_text, page_num_input, query_input, download_file, download_format_input]) # Clear all relevant components, including format

demo.launch(share=True)
