import os
import io
import re
import zipfile
import json
from pathlib import Path
from typing import Dict, Any, List, Optional


def extract_title_and_abstract(text: str, filename: str) -> Dict[str, str]:
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    raw_title = Path(filename).stem.replace("_", " ").replace("-", " ").title()
    
    # Try finding title in first few lines
    title = raw_title
    for l in lines[:5]:
        if len(l) > 10 and not l.lower().startswith(("abstract", "introduction", "author", "arxiv", "volume", "published")):
            # Clean title
            title = l.lstrip("# ").strip()
            break
            
    # Try finding abstract
    abstract = ""
    abs_match = re.search(r'(?:abstract|summary)[:\s]*(.*?)(?:\n\s*(?:1[\.\s]|introduction|keywords|index terms|background|methods)|\Z)', text, re.IGNORECASE | re.DOTALL)
    if abs_match:
        abstract = abs_match.group(1).strip()[:2000]
    elif len(lines) > 2:
        abstract = " ".join(lines[1:6])[:500]

    return {"title": title, "abstract": abstract}


def parse_pdf(data: bytes, filename: str) -> Dict[str, Any]:
    try:
        import fitz
        doc = fitz.open(stream=data, filetype="pdf")
        pages = []
        for i, page in enumerate(doc):
            pages.append(page.get_text())
        full_text = "\n\n".join(pages).strip()
        if not full_text:
            raise ValueError("No text could be extracted from PDF")
        
        info = extract_title_and_abstract(full_text, filename)
        
        # Check PDF metadata if available
        if doc.metadata and doc.metadata.get("title") and len(doc.metadata.get("title", "")) > 5:
            info["title"] = doc.metadata["title"].strip()
            
        return {
            "title": info["title"],
            "abstract": info["abstract"],
            "content": full_text,
            "document_type": "PDF",
            "metadata": {
                "pages": len(pages),
                "pdf_metadata": doc.metadata or {}
            }
        }
    except Exception as e:
        raise ValueError(f"PDF parsing error: {e}")


def parse_markdown_or_txt(data: bytes, filename: str) -> Dict[str, Any]:
    text = data.decode("utf-8", "ignore").strip()
    if not text:
        raise ValueError("Document is empty")
    
    ext = Path(filename).suffix.lower()
    doc_type = "MARKDOWN" if ext in (".md", ".markdown") else "TEXT"
    
    # Check frontmatter in markdown
    frontmatter = {}
    content = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            fm_text = parts[1]
            content = parts[2].strip()
            for line in fm_text.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    frontmatter[k.strip().lower()] = v.strip().strip("\"'")
                    
    info = extract_title_and_abstract(content, filename)
    if "title" in frontmatter and frontmatter["title"]:
        info["title"] = frontmatter["title"]
    if "abstract" in frontmatter and frontmatter["abstract"]:
        info["abstract"] = frontmatter["abstract"]
    if "department" in frontmatter:
        info["department"] = frontmatter["department"]
        
    return {
        "title": info["title"],
        "abstract": info["abstract"],
        "content": content,
        "document_type": doc_type,
        "metadata": {
            "frontmatter": frontmatter
        }
    }


def parse_code_archive(data: bytes, filename: str) -> Dict[str, Any]:
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except Exception as e:
        raise ValueError(f"Invalid ZIP archive: {e}")
        
    namelist = z.namelist()
    code_extensions = {".py", ".ipynb", ".r", ".jl", ".cpp", ".c", ".h", ".java", ".scala", ".ts", ".js", ".sh", ".yaml", ".yml", ".json"}
    readme_candidates = [n for n in namelist if Path(n).name.lower().startswith("readme")]
    
    readme_content = ""
    if readme_candidates:
        # Read the first readme
        readme_candidates.sort(key=lambda x: len(x))
        readme_content = z.read(readme_candidates[0]).decode("utf-8", "ignore")
        
    code_snippets = []
    file_tree = []
    libraries_found = set()
    dataset_references = set()
    
    # Scan files
    for member in namelist[:150]:
        if member.startswith("__MACOSX") or member.endswith("/"):
            continue
        file_tree.append(member)
        p = Path(member)
        if p.suffix.lower() in code_extensions and z.getinfo(member).file_size < 300000:
            try:
                raw_code = z.read(member).decode("utf-8", "ignore")
                
                # Check for datasets in code
                for d in ["mimic", "imagenet", "cifar", "mnist", "tcga", "landsat", "sentinel", "chexpert", "treenet", "urbansound"]:
                    if d in raw_code.lower():
                        dataset_references.add(d.upper())
                
                # Check for ML / DS libraries
                for lib in ["torch", "tensorflow", "keras", "transformers", "scikit-learn", "sklearn", "jax", "spacy", "nltk", "gdal", "rasterio"]:
                    if f"import {lib}" in raw_code or f"from {lib}" in raw_code:
                        libraries_found.add(lib)
                        
                code_snippets.append(f"### File: {member}\n```{p.suffix.lstrip('.')}\n{raw_code[:1500]}\n```")
            except Exception:
                continue

    raw_title = Path(filename).stem.replace("_", " ").replace("-", " ").title()
    title = f"Code Repository: {raw_title}"
    abstract = ""
    
    if readme_content:
        info = extract_title_and_abstract(readme_content, filename)
        if info["title"] and info["title"] != raw_title:
            title = f"Code Repository: {info['title']}"
        abstract = info["abstract"]
    else:
        abstract = f"Research code repository containing {len(file_tree)} files. Detected ML/data libraries: {', '.join(sorted(libraries_found)) or 'Standard library'}. Detected datasets: {', '.join(sorted(dataset_references)) or 'Internal datasets'}."

    combined_text = f"# {title}\n\n## Abstract / Readme Summary\n{abstract}\n\n"
    if readme_content:
        combined_text += f"## Readme Content\n{readme_content[:4000]}\n\n"
    combined_text += f"## Repository File Structure\n" + "\n".join(file_tree[:50]) + "\n\n"
    combined_text += f"## Code Modules & Implementations\n" + "\n\n".join(code_snippets[:10])

    return {
        "title": title,
        "abstract": abstract,
        "content": combined_text,
        "document_type": "CODE_REPO",
        "metadata": {
            "total_files": len(file_tree),
            "libraries": list(libraries_found),
            "datasets": list(dataset_references),
            "files": file_tree[:100]
        }
    }


def parse_document(data: bytes, filename: str) -> Dict[str, Any]:
    fn = filename.lower()
    if fn.endswith(".pdf"):
        return parse_pdf(data, filename)
    elif fn.endswith((".zip", ".tar", ".gz")):
        return parse_code_archive(data, filename)
    elif fn.endswith((".py", ".ipynb", ".r", ".jl", ".cpp", ".js", ".ts")):
        # Single code file
        text = data.decode("utf-8", "ignore")
        title = f"Code Script: {Path(filename).stem.replace('_', ' ').title()}"
        return {
            "title": title,
            "abstract": f"Code script implementing algorithmic workflows in {Path(filename).suffix}.",
            "content": f"# {title}\n\n```{Path(filename).suffix.lstrip('.')}\n{text[:15000]}\n```",
            "document_type": "CODE_SCRIPT",
            "metadata": {"filename": filename}
        }
    elif fn.endswith((".md", ".markdown", ".txt", ".csv", ".json")):
        return parse_markdown_or_txt(data, filename)
    else:
        # Fallback text
        return parse_markdown_or_txt(data, filename)
