# This is extract_us_code_citations_2025-03-19.py


import requests
import PyPDF2
import re
import os
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
import tempfile
from openpyxl import Workbook
from openpyxl.styles import Alignment
from openpyxl.utils import get_column_letter


def download_pdf(url):
    """Downloads a PDF from the given URL and saves it as a temporary file."""
    try:
        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        for chunk in response.iter_content(chunk_size=1024):
            temp_file.write(chunk)
        temp_file.close()
        print(f"Downloaded {url}")
        return temp_file.name
    except Exception as e:
        print(f"Failed to download {url}: {e}")
        return None


def sanitize_text(text):
    """Removes line breaks and carriage returns from a given text."""
    return re.sub(r"[\r\n]+", " ", text).strip()


def clean_citation(citation):
    """Cleans up citation syntax to match standard formats."""
    citation = re.sub(r"\b(\d+)\s*(U\.S\.C\.|USC)\s*(\d+)\b", r"\1 USC \3", citation)
    citation = re.sub(r"\b(\d+)\s*(C\.F\.R\.|CFR)\s*(\d+)\b", r"\1 CFR \3", citation)
    citation = re.sub(r"\b(E\.O\.|Executive\s*Order)\s*(\d+)\b", r"Executive Order \2", citation)
    citation = re.sub(r"\bEO\s+(\d+)\b", r"EO \1", citation)  # Ensure EO includes the number
    return citation


def extract_toc(reader):
    """Attempts to extract the Table of Contents (TOC) from the PDF."""
    toc = []
    toc_pattern = r"(?P<heading>.+?)\s+(\d+)"
    for page_num, page in enumerate(reader.pages[:10]):  # Check the first 10 pages for a TOC
        text = page.extract_text()
        if text and "Table of Contents" in text:
            matches = re.findall(toc_pattern, text)
            for match in matches:
                heading = sanitize_text(match[0])
                page_start = int(match[1])
                toc.append((heading, page_start))
    return toc


def infer_section_name(toc, page_num, context, page_text):
    """Infers the section name based on TOC or contextual headers."""
    if toc:
        for i, (section, start_page) in enumerate(toc):
            if i + 1 < len(toc) and toc[i + 1][1] > page_num >= start_page:
                return section
            elif i == len(toc) - 1 and page_num >= start_page:  # Last TOC entry
                return section


    # Fallback: Find the nearest one-line paragraph before the context
    lines = page_text.splitlines()
    context_start = page_text.find(context)
    for i in range(len(lines) - 1, -1, -1):
        if len(lines[i].strip()) > 0 and lines[i].strip() in page_text[:context_start]:
            return sanitize_text(lines[i])
    return "Unknown Section"


def extract_us_code_citations(pdf_path, url):
    """Extracts U.S. Code, CFR, Executive Order, Acts, and OMB references from a given PDF file."""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            toc = extract_toc(reader)
            num_pages = len(reader.pages)


            citations = []
            for page_num in range(num_pages):
                page = reader.pages[page_num]
                text = page.extract_text()


                if text:
                    # Updated regex pattern to capture all requested references
                    citation_pattern = r"\b(\d+)\s*(U\.S\.C\.|USC|U.S. Code)\s*\u00a7?\s*(\d+(\.\d+)*([a-zA-Z0-9]*)?)|" \
                                       r"\b(\d+)\s*(C\.F\.R\.|CFR|Code of Federal Regulations)\s*\u00a7?\s*(\d+(\.\d+)*([a-zA-Z0-9]*)?)|" \
                                       r"(E\.O\.|Executive\s*Order)\s*(\d+)|" \
                                       r"\bEO\s+(\d+)\b|" \
                                       r"\bAct\s+" \
                                       r"|\sUSC\b" \
                                       r"|
