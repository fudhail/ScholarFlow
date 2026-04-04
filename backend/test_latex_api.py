import requests
import os

tex_doc = r"""\documentclass[conference]{IEEEtran}
\begin{document}
\title{Test API Compilation}
\author{\IEEEauthorblockN{Test Author}}
\maketitle
\begin{abstract}
This is a test abstract.
\end{abstract}
\section{Introduction}
Testing IEEEtran class via API.
\end{document}
"""

try:
    print("Testing latexonline.cc...")
    res = requests.post("https://latexonline.cc/compile", data={"text": tex_doc, "command": "pdflatex"})
    if res.status_code == 200:
        with open("test_api.pdf", "wb") as f:
            f.write(res.content)
        print("Success! File saved as test_api.pdf")
    else:
        print(f"Failed. Status: {res.status_code}")
        print(res.text[:500])
except Exception as e:
    print(f"Error: {e}")
