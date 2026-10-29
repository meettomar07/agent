"""HTML document text and section extractor."""

from typing import Any, Dict, List, Tuple
from bs4 import BeautifulSoup


class HtmlDocumentExtractor:
    """Extracts clean text and paragraphs from official notification HTML pages."""

    @staticmethod
    def extract(html_content: str) -> Tuple[str, List[Dict[str, Any]], int]:
        """Extract main body text and structured paragraphs from HTML.

        Returns:
            Tuple of (full_text, pages_list, page_count)
            where pages_list contains page 1 with paragraphs.
        """
        soup = BeautifulSoup(html_content, "html.parser")

        # Strip scripts, styles, navs, footers
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()

        # Find main content container if present, else fallback to body
        main = soup.find("main") or soup.find("article") or soup.find("div", {"id": ["content", "main-content"]}) or soup.body

        if not main:
            clean_text = soup.get_text(separator="\n").strip()
        else:
            clean_text = main.get_text(separator="\n").strip()

        # Format paragraphs
        lines = [line.strip() for line in clean_text.splitlines() if line.strip()]
        full_text = "\n".join(lines)

        # Extract HTML tables
        html_tables = []
        for t_idx, tbl in enumerate(soup.find_all("table")):
            rows = []
            for tr in tbl.find_all("tr"):
                cells = [cell.get_text(separator=" ", strip=True) for cell in tr.find_all(["th", "td"])]
                if any(cells):
                    rows.append(cells)
            if len(rows) >= 2:
                html_tables.append({
                    "page_number": 1,
                    "table_index": t_idx + 1,
                    "header": rows[0],
                    "rows": rows,
                    "row_count": len(rows),
                    "col_count": len(rows[0]),
                })

        pages = [
            {
                "page_number": 1,
                "text": full_text,
                "document_tables": html_tables,
            }
        ]

        return full_text, pages, 1
