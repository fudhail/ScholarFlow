import urllib.request
import urllib.parse
import sys

full_tex = r"""\documentclass[conference]{IEEEtran}
\begin{document}
\title{Test Title}
\author{\IEEEauthorblockN{Test Author}}
\maketitle
\begin{abstract}
Test abstract
\end{abstract}
\section{Intro}
test
\end{document}
"""

try:
    print("Sending POST to latexonline.cc...")
    data = urllib.parse.urlencode({"text": full_tex, "command": "pdflatex"}).encode("utf-8")
    req = urllib.request.Request("https://latexonline.cc/compile", data=data)
    with urllib.request.urlopen(req, timeout=30) as response:
        if response.status == 200:
            print("Success! 200 OK")
        else:
            print(f"Failed with status: {response.status}")
except urllib.error.HTTPError as e:
    print(f"HTTPError: {e.code} - {e.reason}")
    print("Response body:")
    print(e.read().decode('utf-8'))
except Exception as e:
    print(f"Other Error: {e}")
