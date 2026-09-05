import markdown
import os

md_path = r"C:\Srinidh\civil\Extended_Structural_Calculation_Reference.md"
html_path = r"C:\Srinidh\civil\Extended_Structural_Calculation_Reference.html"

with open(md_path, 'r', encoding='utf-8') as f:
    text = f.read()

# MathJax config and HTML template
html_template = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Structural Calculation Reference</title>
<script src="https://polyfill.io/v3/polyfill.min.js?features=es6"></script>
<script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
<style>
    body {
        font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        line-height: 1.6;
        color: #333;
        max-width: 900px;
        margin: 0 auto;
        padding: 40px;
    }
    h1 {
        color: #2c3e50;
        border-bottom: 2px solid #3498db;
        padding-bottom: 10px;
    }
    h2 {
        color: #2980b9;
        margin-top: 30px;
        border-bottom: 1px solid #ecf0f1;
        padding-bottom: 5px;
    }
    h3 {
        color: #34495e;
    }
    .math-display {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 5px;
        overflow-x: auto;
        margin: 15px 0;
    }
    @media print {
        body { padding: 0; }
        .math-display { background-color: transparent; }
    }
</style>
</head>
<body>
{{CONTENT}}
</body>
</html>"""

# We need to ensure that markdown parser doesn't mangle LaTeX math.
# A simple way is to replace \[ \] and \( \) blocks with something safe, parse markdown, then restore.
# Or just let markdown parse it and hope it leaves the LaTeX alone (it usually mostly does if separated by empty lines).

# Convert the markdown to HTML
html_content = markdown.markdown(text)

# Replace \[ ... \] with div class math-display
html_content = html_content.replace('\\[', '<div class="math-display">\\[').replace('\\]', '\\]</div>')

final_html = html_template.replace("{{CONTENT}}", html_content)

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(final_html)

print("HTML generated.")
