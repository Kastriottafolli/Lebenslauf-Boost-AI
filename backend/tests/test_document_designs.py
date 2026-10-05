"""Exported designs retain long Unicode source text across page breaks."""

from io import BytesIO

from docx import Document
from pypdf import PdfReader

from backend.services.export_service import _DESIGNS, to_docx, to_pdf


def test_all_designs_preserve_unicode_and_last_entry_in_pdf_and_word():
    content = "# Alex Beispiel\nSenior Developer\n\n## Überblick / Përvoja\n" + "\n".join(
        f"- Projekt {i}: Grüße und aftësi – {i} bestätigte Aufgaben."
        for i in range(1, 121)
    )
    for design in _DESIGNS:
        pdf = PdfReader(BytesIO(to_pdf(content, design)))
        assert len(pdf.pages) > 1
        text = "\n".join(page.extract_text() for page in pdf.pages)
        assert "Alex Beispiel" in text
        assert "Projekt 120: Grüße und aftësi" in text
        word = Document(BytesIO(to_docx(content, design)))
        text = "\n".join(p.text for p in word.paragraphs)
        assert "Alex Beispiel" in text
        assert "Projekt 120: Grüße und aftësi" in text
