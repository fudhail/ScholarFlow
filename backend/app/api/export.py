from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import tempfile
import pypandoc
import subprocess
import shutil
import logging
import sys
import urllib.error
import urllib.request
import urllib.parse
from typing import List, Optional
import re
from pathlib import Path
import uuid

router = APIRouter(prefix="/export", tags=["export"])
logger = logging.getLogger(__name__)

class Block(BaseModel):
    id: str
    type: str # title, authors, abstract, keywords, section
    heading: Optional[str] = None
    content: str

class ExportRequest(BaseModel):
    latex: str
    template: str # 'IEEE' or 'SPRINGER'

def cleanup_temp_dir(dir_path: str):
    try:
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
    except Exception as e:
        logger.error(f"Failed to cleanup {dir_path}: {e}")

SUPPORTED_EXPORT_TEMPLATES = {"IEEE", "SPRINGER"}


def normalize_template_key(template: str) -> str:
    return (template or "IEEE").strip().upper()


def resolve_ieee_class_path() -> Optional[Path]:
    repo_root = Path(__file__).resolve().parents[3]
    candidates = [
        repo_root / "docs" / "IEEEtran.cls",
        repo_root / "docs" / "oldd" / "IEEEtran.cls",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def is_valid_pdf(pdf_file: str) -> bool:
    if not os.path.exists(pdf_file) or os.path.getsize(pdf_file) < 5:
        return False
    try:
        with open(pdf_file, "rb") as f:
            return f.read(5) == b"%PDF-"
    except Exception:
        return False


def read_text_head(path: str, limit: int = 300) -> str:
    if not os.path.exists(path):
        return ""
    try:
        with open(path, "rb") as f:
            raw = f.read(limit)
        return raw.decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""


def should_attempt_cloud_fallback(stdout: str, stderr: str, log_tail: str, returncode: int) -> bool:
    combined = "\n".join([stdout, stderr, log_tail]).lower()
    environment_markers = [
        "miktex",
        "fresh tex installation",
        "please finish the setup before proceeding",
        "access is denied",
        "security risk: running with elevated privileges",
        "cannot retrieve attributes for the directory",
        "this process finishes with exit code 1",
    ]
    if any(marker in combined for marker in environment_markers):
        return True
    # MiKTeX can fail before it even writes a log; treat that as infrastructure, not user LaTeX.
    if not log_tail and returncode in {1, 3221226505, 3221225477}:
        return True
    return False


def ensure_pdf_output(pdf_file: str, source_name: str):
    if is_valid_pdf(pdf_file):
        return
    head = read_text_head(pdf_file)
    detail = f"{source_name} did not return a valid PDF."
    if head:
        detail += f" Output started with: {head[:200]}"
    raise HTTPException(status_code=500, detail=detail)


def build_multipart_form_data(fields: List[tuple[str, str]]) -> tuple[bytes, str]:
    boundary = f"----ScholarFlowBoundary{uuid.uuid4().hex}"
    body = bytearray()

    for name, value in fields:
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        body.extend(value.encode("utf-8"))
        body.extend(b"\r\n")

    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    return bytes(body), f"multipart/form-data; boundary={boundary}"

def convert_md_to_tex(text: str) -> str:
    if not text: return ""
    # Safe simple regex fallback for when Pandoc is missing
    # Convert bold
    text = re.sub(r'\*\*(.*?)\*\*', r'\\textbf{\1}', text)
    # Convert italic
    text = re.sub(r'\*(.*?)\*', r'\\textit{\1}', text)
    
    # We shouldn't escape everything blindly if the user expects to write raw LaTeX, 
    # but let's handle basic newlines
    text = text.replace('\n\n', '\n\n')
    
    return text

def build_pdflatex_env(temp_dir: str) -> dict:
    env = os.environ.copy()
    env["TMP"] = temp_dir
    env["TEMP"] = temp_dir

    home = env.get("USERPROFILE") or str(Path.home())
    if home.lower().endswith(".exe") or not os.path.isdir(home):
        home = str(Path.home())

    env["HOME"] = home
    env["USERPROFILE"] = home
    env.setdefault("HOMEDRIVE", os.path.splitdrive(home)[0] or "C:")
    env.setdefault("HOMEPATH", home[len(env["HOMEDRIVE"]):] if home.startswith(env["HOMEDRIVE"]) else "\\Users")

    # Ensure MiKTeX can write to a valid cache/config tree
    local_app_data = env.get("LOCALAPPDATA")
    if not local_app_data or local_app_data.lower().endswith(".exe"):
        local_app_data = os.path.join(home, "AppData", "Local")
    env["LOCALAPPDATA"] = local_app_data

    # Avoid problematic inherited interpreter env values when launching pdflatex
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONPATH", None)
    return env

def read_latex_log(log_file: str) -> str:
    if not os.path.exists(log_file):
        return ""
    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            data = f.read()
        return data[-4000:]
    except Exception:
        return ""

def compile_via_cloud(full_tex: str, pdf_file: str):
    import urllib.request
    import urllib.error

    data, content_type = build_multipart_form_data([
        ("filecontents[]", full_tex),
        ("filename[]", "document.tex"),
        ("engine", "pdflatex"),
        ("return", "pdf"),
    ])

    req = urllib.request.Request(
        "https://texlive.net/cgi-bin/latexcgi",
        data=data,
        headers={"Content-Type": content_type},
    )
    with urllib.request.urlopen(req, timeout=45) as response:
        if response.status != 200:
            raise Exception(f"Failed with status: {response.status}")
        with open(pdf_file, "wb") as f:
            f.write(response.read())

    ensure_pdf_output(pdf_file, "Cloud LaTeX compiler")


def prepare_latex_assets(full_tex: str, temp_dir: str) -> str:
    """
    Rewrite \includegraphics paths marked with __ASSET__ and materialize files locally,
    so pdflatex can render uploaded assets.
    """
    pattern = re.compile(r"(\\includegraphics(?:\[[^\]]*\])?\{)__ASSET__([^\}]+)(\})")
    assets_dir = Path(temp_dir) / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    repo_root = Path(__file__).resolve().parents[3]
    upload_roots = [repo_root / "uploads", repo_root / "backend" / "uploads"]
    asset_idx = 0

    def _copy_for_path(asset_path: str) -> str:
        nonlocal asset_idx
        decoded = urllib.parse.unquote(asset_path.strip())
        src = None

        if decoded.startswith("http://") or decoded.startswith("https://"):
            parsed = urllib.parse.urlparse(decoded)
            if parsed.path.startswith("/uploads/"):
                rel = parsed.path[len("/uploads/"):].lstrip("/")
                for root in upload_roots:
                    candidate = root / rel
                    if candidate.exists():
                        src = candidate
                        break
            if src is None:
                ext = Path(parsed.path).suffix or ".bin"
                target = assets_dir / f"asset_{asset_idx}{ext}"
                asset_idx += 1
                urllib.request.urlretrieve(decoded, str(target))
                return f"assets/{target.name}"
        else:
            norm = decoded.replace("\\", "/")
            if norm.startswith("/uploads/"):
                rel = norm[len("/uploads/"):].lstrip("/")
                for root in upload_roots:
                    candidate = root / rel
                    if candidate.exists():
                        src = candidate
                        break
            else:
                path_obj = Path(norm)
                if path_obj.exists():
                    src = path_obj

        if src is None:
            raise FileNotFoundError(f"Asset not found for includegraphics path: {decoded}")

        ext = src.suffix or ".bin"
        target = assets_dir / f"asset_{asset_idx}{ext}"
        asset_idx += 1
        shutil.copy(src, target)
        return f"assets/{target.name}"

    def _repl(match: re.Match) -> str:
        prefix, raw_path, suffix = match.group(1), match.group(2), match.group(3)
        try:
            local_path = _copy_for_path(raw_path)
            return f"{prefix}{local_path}{suffix}"
        except Exception as e:
            logger.warning(f"Failed to materialize LaTeX asset '{raw_path}': {e}")
            return f"{prefix}{raw_path}{suffix}"

    return pattern.sub(_repl, full_tex)

@router.post("/pdf")
async def export_pdf(request: ExportRequest, background_tasks: BackgroundTasks):
    """
    Export the provided blocks to a PDF using LaTeX.
    Downloads the PDF directly to the user's browser.
    """
    template_key = normalize_template_key(request.template)
    if template_key not in SUPPORTED_EXPORT_TEMPLATES:
        raise HTTPException(status_code=400, detail=f"Unsupported export template '{request.template}'.")

    full_tex = request.latex
    needs_ieee_class = template_key == "IEEE" or "IEEEtran" in full_tex

    # 3. Compile to PDF in a temporary directory
    temp_dir = tempfile.mkdtemp()
    background_tasks.add_task(cleanup_temp_dir, temp_dir)

    tex_file = os.path.join(temp_dir, "manuscript.tex")
    pdf_file = os.path.join(temp_dir, "manuscript.pdf")
    log_file = os.path.join(temp_dir, "manuscript.log")
    
    # Copy template support files only when the LaTeX source actually needs them.
    if needs_ieee_class:
        cls_path = resolve_ieee_class_path()
        if cls_path is None:
            raise HTTPException(status_code=500, detail="IEEE export support file IEEEtran.cls is missing on the server.")
        shutil.copy(cls_path, os.path.join(temp_dir, "IEEEtran.cls"))

    full_tex = prepare_latex_assets(full_tex, temp_dir)
    with open(tex_file, "w", encoding="utf-8") as f:
        f.write(full_tex)

    # Run pdflatex twice for cross-references to resolve
    pdflatex_env = build_pdflatex_env(temp_dir)
    try:
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "manuscript.tex"],
            cwd=temp_dir,
            check=True,
            env=pdflatex_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "manuscript.tex"],
            cwd=temp_dir,
            check=True,
            env=pdflatex_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    except subprocess.CalledProcessError as e:
        stdout = e.stdout.decode(errors="ignore")
        stderr = e.stderr.decode(errors="ignore")
        log_tail = read_latex_log(log_file)
        logger.error(f"pdflatex failed: {stdout} \n {stderr} \n LOG_TAIL:\n{log_tail}")
        if should_attempt_cloud_fallback(stdout, stderr, log_tail, e.returncode):
            logger.warning("Local TeX environment issue detected. Falling back to cloud LaTeX compiler.")
            try:
                compile_via_cloud(full_tex, pdf_file)
            except Exception as cloud_err:
                logger.error(f"Cloud fallback failed after local compiler error: {cloud_err}")
                raise HTTPException(status_code=500, detail=f"Local TeX compiler failed and cloud fallback failed: {str(cloud_err)}")
        else:
            raise HTTPException(status_code=500, detail="pdflatex compilation failed. Check LaTeX syntax and unsupported characters.")
    except FileNotFoundError:
        logger.warning("pdflatex command not found. Attempting cloud compiler fallback (latexonline.cc)...")
        try:
            compile_via_cloud(full_tex, pdf_file)
        except urllib.error.HTTPError as he:
            err_body = he.read().decode('utf-8', errors='ignore')
            logger.error(f"Cloud fallback HTTP Error: {he.code} {he.reason} - {err_body}")
            raise HTTPException(status_code=500, detail=f"Cloud LaTeX API Error: {he.code} {he.reason}. Output: {err_body[:200]}")
        except Exception as cloud_err:
            logger.error(f"Cloud fallback failed: {cloud_err}")
            raise HTTPException(status_code=500, detail=f"Cloud fallback failed: {str(cloud_err)}")

    if not os.path.exists(pdf_file):
        raise HTTPException(status_code=500, detail="PDF file was not generated.")
    ensure_pdf_output(pdf_file, "LaTeX compiler")

    return FileResponse(
        path=pdf_file,
        filename=f"{template_key}_Manuscript.pdf",
        media_type="application/pdf"
    )
