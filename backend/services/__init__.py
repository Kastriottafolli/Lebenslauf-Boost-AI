"""Service-Schicht — die Geschäftslogik der App.

Jeder Service ist für genau einen Bereich zuständig:

    session_service     Sitzungen anlegen und laden
    document_service    Lebenslauf-Upload: Text/Foto extrahieren, RAG-Index aufbauen
    extraction_service  Text- und Foto-Extraktion aus PDF/DOCX/TXT
    rag_service         Chunking, Embeddings/TF-IDF, Retrieval, Keyword-/ATS-Analyse
    generation_service  Lebenslauf generieren, vergleichen und verfeinern
    export_service      Export als PDF (ReportLab) oder Word (python-docx)
"""
