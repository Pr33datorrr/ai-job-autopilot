import os
import re
import subprocess

# Paths relative to project root
TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "..", "templates", "template.tex")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")


# ------------------------------------------------------------------
# LaTeX sanitisation
# ------------------------------------------------------------------

# Order matters: backslash must NOT be escaped here because the
# template itself is valid LaTeX - we only escape characters that
# the LLM might inject in free-text bullet strings.
_LATEX_SPECIAL = {
    "%": r"\%",
    "&": r"\&",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
}

_LATEX_RE = re.compile("|".join(re.escape(k) for k in _LATEX_SPECIAL))


def escape_latex(text: str) -> str:
    """
    Escape reserved LaTeX characters in *text* so it compiles safely.
    Handles: % & $ # _ { }
    """
    return _LATEX_RE.sub(lambda m: _LATEX_SPECIAL[m.group()], text)


# ------------------------------------------------------------------
# PDF generation
# ------------------------------------------------------------------

def generate_pdf(company_name: str, tailored_bullets_list: list) -> dict:
    """
    Inject *tailored_bullets_list* into the LaTeX template,
    compile to PDF, and return a status dict.

    Parameters
    ----------
    company_name : str
        Used only for logging / future filename customisation.
    tailored_bullets_list : list[str]
        Exactly 5 bullet-point strings to inject.

    Returns
    -------
    dict
        ``{"status": "success", "pdf_path": ...}`` on success, or
        ``{"status": "failed", "tex_path": ..., "error": ...}`` on failure.
    """
    # --- 1.  Read template ------------------------------------------------
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        tex = f.read()

    # --- 2.  Sanitise & inject -------------------------------------------
    for i, bullet in enumerate(tailored_bullets_list[:5], start=1):
        placeholder = f"[[BULLET{i}]]"
        tex = tex.replace(placeholder, escape_latex(bullet))

    # --- 3.  Write modified .tex -----------------------------------------
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    tex_path = os.path.join(OUTPUT_DIR, "modified_template.tex")
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(tex)

    print(f"[pdf_generator] Wrote modified template -> {tex_path}")

    # --- 4.  Compile with pdflatex --------------------------------------
    pdf_path = os.path.join(OUTPUT_DIR, "modified_template.pdf")

    try:
        result = subprocess.run(
            [
                "pdflatex",
                "-interaction=nonstopmode",
                f"-output-directory={OUTPUT_DIR}",
                tex_path,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode == 0:
            print(f"[pdf_generator] PDF compiled successfully -> {pdf_path}")
            return {"status": "success", "pdf_path": pdf_path}
        else:
            error_snippet = (result.stdout + result.stderr)[-500:]
            print(f"[pdf_generator] pdflatex exited with code {result.returncode}")
            print(f"[pdf_generator] Tail of log:\n{error_snippet}")
            return {
                "status": "failed",
                "tex_path": tex_path,
                "error": "Compilation failed.",
            }

    except FileNotFoundError:
        msg = "pdflatex not found on PATH. Install a TeX distribution (e.g. MiKTeX or TeX Live)."
        print(f"[pdf_generator] {msg}")
        return {"status": "failed", "tex_path": tex_path, "error": msg}

    except subprocess.TimeoutExpired:
        msg = "pdflatex timed out after 120 s."
        print(f"[pdf_generator] {msg}")
        return {"status": "failed", "tex_path": tex_path, "error": msg}

    except Exception as exc:
        msg = f"Unexpected error during compilation: {exc}"
        print(f"[pdf_generator] {msg}")
        return {"status": "failed", "tex_path": tex_path, "error": msg}


# ======================================================================
# CLI entry-point
# ======================================================================

if __name__ == "__main__":
    test_bullets = [
        "Engineered a Python-based automation framework that reduced ticket resolution latency by 250%, saving approximately 40 engineering hours per week.",
        "Optimized complex SQL queries on MS SQL Server for datasets exceeding 10M+ rows, achieving a 40% improvement in query execution time.",
        "Designed & deployed 12+ automated SAP workflows using Python and ABAP, eliminating manual data entry for finance teams.",
        "Strengthened enterprise data security by conducting rigorous audit cycles, reducing system vulnerabilities by 25% across 3 SAP modules.",
        "Collaborated with a cross-functional team of 8 engineers across 3 time zones to deliver quarterly platform upgrades on schedule.",
    ]

    outcome = generate_pdf("TestCorp", test_bullets)
    print(f"\nResult: {outcome}")
