"""
Convert RESEARCH_TOPICS.md to PDF with proper formatting
Uses xhtml2pdf (pisa) which is pure Python and works on Windows
"""
from markdown import markdown
from xhtml2pdf import pisa
from pathlib import Path
import io

def md_to_pdf(md_file, pdf_file):
    """Convert markdown to PDF with styling"""
    
    # Read markdown file
    with open(md_file, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    # Convert markdown to HTML
    html_content = markdown(md_content, extensions=['tables', 'fenced_code', 'extra'])
    
    # CSS styling for professional PDF
    css = """
    <style>
    @page {
        size: a4;
        margin: 2cm;
    }
    
    body {
        font-family: Georgia, 'Times New Roman', serif;
        font-size: 11pt;
        line-height: 1.6;
        color: #333;
    }
    
    h1 {
        color: #1a1a1a;
        font-size: 20pt;
        border-bottom: 3px solid #2c5aa0;
        padding-bottom: 8px;
        margin-top: 25px;
        margin-bottom: 15px;
    }
    
    h2 {
        color: #2c5aa0;
        font-size: 16pt;
        margin-top: 20px;
        margin-bottom: 12px;
        border-bottom: 2px solid #e0e0e0;
        padding-bottom: 6px;
    }
    
    h3 {
        color: #333;
        font-size: 13pt;
        margin-top: 15px;
        margin-bottom: 8px;
    }
    
    p {
        text-align: justify;
        margin-bottom: 10px;
    }
    
    ul, ol {
        margin-left: 20px;
        margin-bottom: 12px;
    }
    
    li {
        margin-bottom: 6px;
    }
    
    code {
        background-color: #f4f4f4;
        padding: 2px 5px;
        font-family: Consolas, Monaco, monospace;
        font-size: 9pt;
        color: #c7254e;
    }
    
    pre {
        background-color: #f8f8f8;
        border: 1px solid #ddd;
        padding: 12px;
        margin-bottom: 15px;
        font-size: 9pt;
    }
    
    pre code {
        background-color: transparent;
        padding: 0;
        color: #333;
    }
    
    table {
        border-collapse: collapse;
        width: 100%;
        margin-bottom: 15px;
        font-size: 10pt;
    }
    
    th {
        background-color: #2c5aa0;
        color: white;
        padding: 10px;
        text-align: left;
        font-weight: bold;
    }
    
    td {
        border: 1px solid #ddd;
        padding: 8px;
    }
    
    tr:nth-child(even) {
        background-color: #f9f9f9;
    }
    
    strong {
        color: #1a1a1a;
        font-weight: 600;
    }
    
    em {
        font-style: italic;
        color: #555;
    }
    
    hr {
        border: none;
        border-top: 2px solid #e0e0e0;
        margin: 25px 0;
    }
    
    blockquote {
        border-left: 4px solid #2c5aa0;
        padding-left: 15px;
        margin: 15px 0;
        color: #555;
        font-style: italic;
    }
    </style>
    """
    
    # Create full HTML document
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Research Topics - ScholarFlow</title>
        {css}
    </head>
    <body>
        {html_content}
    </body>
    </html>
    """
    
    # Convert to PDF
    with open(pdf_file, 'wb') as output_file:
        pisa_status = pisa.CreatePDF(
            full_html,
            dest=output_file,
            encoding='utf-8'
        )
    
    if pisa_status.err:
        print(f"❌ Error creating PDF: {pisa_status.err}")
        return False
    else:
        print(f"✅ PDF created successfully: {pdf_file}")
        return True

if __name__ == "__main__":
    # Go up 3 levels: scripts -> backend -> scholarflow -> docs
    md_file = Path(__file__).parent.parent.parent / "docs" / "LANGGRAPH_SETUP.md"
    pdf_file = Path(__file__).parent.parent.parent / "docs" / "LANGGRAPH_SETUP.pdf"
    
    md_to_pdf(md_file, pdf_file)
