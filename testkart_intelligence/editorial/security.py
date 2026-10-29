"""Security controls, host validation, input sanitization, and safe rendering for Editorial Review."""

import html
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
from fastapi import Request, HTTPException

from testkart_intelligence.config import settings
from testkart_intelligence.security.allowlist import is_official_domain


class EditorialSecurityError(Exception):
    """Raised when an editorial security invariant is violated."""
    pass


ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1", "testclient", "testserver"}


def validate_editorial_request(request: Request) -> None:
    """Validate that requests to editorial endpoints originate from localhost only."""
    client_host = request.client.host if request.client else "unknown"
    client_clean = client_host.split(":")[0].lower() if ":" in client_host and not client_host.startswith("::") else client_host.lower()

    if client_clean not in ALLOWED_HOSTS and client_host not in ALLOWED_HOSTS:
        raise HTTPException(
            status_code=403,
            detail=f"Forbidden: Editorial dashboard is restricted to localhost (got client IP '{client_host}')",
        )

    # Validate Host header
    raw_host = request.headers.get("host", "").split(":")[0].lower()
    if raw_host and raw_host not in ALLOWED_HOSTS:
        raise HTTPException(
            status_code=403,
            detail=f"Forbidden: Host header '{raw_host}' is not an authorized local host",
        )

    # For state-changing operations, validate Origin / Referer
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        origin = request.headers.get("origin")
        if origin:
            parsed = urlparse(origin)
            origin_host = (parsed.hostname or "").lower()
            if origin_host not in ALLOWED_HOSTS:
                raise HTTPException(
                    status_code=403,
                    detail=f"Forbidden: Untrusted request origin '{origin}'",
                )

        referer = request.headers.get("referer")
        if referer:
            parsed_ref = urlparse(referer)
            ref_host = (parsed_ref.hostname or "").lower()
            if ref_host not in ALLOWED_HOSTS:
                raise HTTPException(
                    status_code=403,
                    detail=f"Forbidden: Untrusted request referer '{referer}'",
                )


def escape_html(text: Optional[str]) -> str:
    """Safely escape text for HTML output, preventing XSS injection."""
    if text is None:
        return ""
    return html.escape(str(text), quote=True)


def is_safe_document_path(file_path_str: Optional[str]) -> Optional[Path]:
    """Verify that a document path exists and is confined within application data directories."""
    if not file_path_str:
        return None
    try:
        resolved = Path(file_path_str).resolve()
        if not resolved.exists() or not resolved.is_file():
            return None
        # Confine to BASE_DIR or DATA_DIR to block path traversal
        base_resolved = settings.BASE_DIR.resolve()
        data_resolved = settings.DATA_DIR.resolve()
        if resolved.is_relative_to(base_resolved) or resolved.is_relative_to(data_resolved):
            return resolved
    except (ValueError, OSError):
        return None
    return None


def is_safe_official_url(url: Optional[str]) -> bool:
    """Verify whether a URL points strictly to an authorized government domain."""
    if not url:
        return False
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = (parsed.hostname or "").lower()
        if not hostname:
            return False
        return is_official_domain(hostname)
    except Exception:
        return False


def safe_render_markdown(md_text: str) -> str:
    """Convert Markdown to safe HTML, strictly escaping all raw HTML tags and neutralizing XSS."""
    if not md_text:
        return ""

    # Neutralize dangerous event handler patterns (onerror=, onload=, onclick=, etc.)
    cleaned = re.sub(r"(?i)\bon\w+\s*=", "data-blocked-event=", md_text)

    # 1. Strictly escape all raw HTML characters first
    text = html.escape(cleaned, quote=True)

    # 2. Extract and preserve code blocks
    code_blocks = []
    def save_code_block(match):
        idx = len(code_blocks)
        code_blocks.append(f"<pre class='code-block'><code>{match.group(1)}</code></pre>")
        return f"__CODE_BLOCK_{idx}__"

    text = re.sub(r"```(?:\w+)?\n?(.*?)```", save_code_block, text, flags=re.DOTALL)

    # 3. Inline code
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)

    # 4. Headers (#, ##, ###, ####)
    text = re.sub(r"^####\s+(.*?)$", r"<h4>\1</h4>", text, flags=re.MULTILINE)
    text = re.sub(r"^###\s+(.*?)$", r"<h3>\1</h3>", text, flags=re.MULTILINE)
    text = re.sub(r"^##\s+(.*?)$", r"<h2>\1</h2>", text, flags=re.MULTILINE)
    text = re.sub(r"^#\s+(.*?)$", r"<h1>\1</h1>", text, flags=re.MULTILINE)

    # 5. Bold and Italic
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)

    # 6. Blockquotes
    text = re.sub(r"^&gt;\s?(.*?)$", r"<blockquote>\1</blockquote>", text, flags=re.MULTILINE)

    # 7. Safe Links [text](url) - reject javascript:, data:, vbscript:
    def format_link(match):
        link_text = match.group(1)
        raw_url = match.group(2).strip()
        # In escaped text, quotes are &quot; etc
        clean_url = html.unescape(raw_url).strip()
        parsed = urlparse(clean_url)
        if parsed.scheme in ("http", "https") or clean_url.startswith("/"):
            safe_target = html.escape(clean_url, quote=True)
            return f'<a href="{safe_target}" target="_blank" rel="noopener noreferrer">{link_text}</a>'
        return f'{link_text} ({html.escape(clean_url, quote=True)})'

    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", format_link, text)

    # 8. Markdown Tables
    lines = text.split("\n")
    in_table = False
    html_lines = []
    table_rows = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            # Check if this is a separator row (e.g. |---|---|)
            if all(re.match(r"^:?-+:?$", c) for c in cells):
                continue
            table_rows.append(cells)
            in_table = True
        else:
            if in_table:
                # Flush table
                html_lines.append("<div class='table-responsive'><table class='editorial-table'>")
                if table_rows:
                    html_lines.append("<thead><tr>" + "".join(f"<th>{c}</th>" for c in table_rows[0]) + "</tr></thead>")
                    html_lines.append("<tbody>")
                    for row in table_rows[1:]:
                        html_lines.append("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>")
                    html_lines.append("</tbody>")
                html_lines.append("</table></div>")
                table_rows = []
                in_table = False
            html_lines.append(line)

    if in_table:
        html_lines.append("<div class='table-responsive'><table class='editorial-table'>")
        if table_rows:
            html_lines.append("<thead><tr>" + "".join(f"<th>{c}</th>" for c in table_rows[0]) + "</tr></thead>")
            html_lines.append("<tbody>")
            for row in table_rows[1:]:
                html_lines.append("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>")
            html_lines.append("</tbody>")
        html_lines.append("</table></div>")

    text = "\n".join(html_lines)

    # 9. Lists
    text = re.sub(r"^\s*-\s+(.*?)$", r"<li>\1</li>", text, flags=re.MULTILINE)
    text = re.sub(r"((?:<li>.*?</li>\n?)+)", r"<ul>\1</ul>", text)

    # 10. Paragraphs
    paragraphs = []
    for chunk in text.split("\n\n"):
        chunk = chunk.strip()
        if not chunk:
            continue
        if chunk.startswith("<h") or chunk.startswith("<ul") or chunk.startswith("<blockquote") or chunk.startswith("<div") or chunk.startswith("__CODE_BLOCK_"):
            paragraphs.append(chunk)
        else:
            paragraphs.append(f"<p>{chunk.replace(chr(10), '<br>')}</p>")

    final_html = "\n".join(paragraphs)

    # 11. Restore code blocks
    for idx, block in enumerate(code_blocks):
        final_html = final_html.replace(f"__CODE_BLOCK_{idx}__", block)

    return final_html
