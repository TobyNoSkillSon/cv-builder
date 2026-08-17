from __future__ import annotations

import hashlib
from pathlib import Path

import pymupdf as fitz


class VerificationError(RuntimeError):
    pass


def verify_pdf(
    pdf: Path,
    *,
    applicant_name: str,
    pages: int = 1,
    min_bottom_mm: float = 10.0,
    min_visible_font_pt: float = 7.5,
) -> dict[str, object]:
    failures: list[str] = []
    suspicious: list[dict[str, object]] = []
    page_reports: list[dict[str, object]] = []
    links: list[str] = []
    with fitz.open(pdf) as document:
        all_text = "\n".join(page.get_text("text") for page in document)
        first = " ".join(all_text.split())[:400]
        if len(document) != pages:
            failures.append(f"expected {pages} page(s), found {len(document)}")
        if " ".join(applicant_name.split()) not in first:
            failures.append(f"applicant name missing from first 400 characters: {applicant_name!r}")
        min_bottom_pt = min_bottom_mm * 72 / 25.4
        for index, page in enumerate(document):
            if abs(page.rect.width - 595.0) > 1.0 or abs(page.rect.height - 842.0) > 1.0:
                failures.append(f"page {index + 1} is not A4: {page.rect.width:.2f} x {page.rect.height:.2f} pt")
            blocks = page.get_text("blocks", sort=True)
            max_y = max((block[3] for block in blocks), default=0.0)
            clearance = page.rect.height - max_y
            if clearance < min_bottom_pt:
                clearance_mm = clearance * 25.4 / 72
                failures.append(
                    f"page {index + 1} bottom clearance is {clearance_mm:.2f} mm; "
                    f"minimum is {min_bottom_mm:.2f} mm"
                )
            links.extend(item.get("uri") for item in page.get_links() if item.get("uri"))
            for block in page.get_text("dict", clip=fitz.INFINITE_RECT()).get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if not text:
                            continue
                        x0, y0, x1, y1 = span["bbox"]
                        reasons: list[str] = []
                        if x0 < -0.5 or y0 < -0.5 or x1 > page.rect.width + 0.5 or y1 > page.rect.height + 0.5:
                            reasons.append("off-page")
                        if span.get("size", 0) < min_visible_font_pt:
                            reasons.append("microscopic")
                        if span.get("alpha", 255) == 0:
                            reasons.append("transparent")
                        if (span.get("color", 0) & 0xFFFFFF) == 0xFFFFFF:
                            reasons.append("white")
                        if reasons:
                            suspicious.append({"page": index + 1, "text": text[:80], "reasons": reasons})
            page_reports.append({
                "page": index + 1,
                "width_pt": round(page.rect.width, 2),
                "height_pt": round(page.rect.height, 2),
                "bottom_clearance_pt": round(clearance, 2),
                "characters": len(page.get_text("text")),
            })
        for required in ("mailto:", "tel:"):
            if not any(uri.startswith(required) for uri in links):
                failures.append(f"missing link with prefix {required!r}")
        if suspicious:
            failures.append(f"found {len(suspicious)} suspicious text span(s)")
    return {
        "ok": not failures,
        "pdf": str(pdf),
        "sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
        "pages": page_reports,
        "links": links,
        "failures": failures,
        "suspicious_spans": suspicious[:20],
    }
