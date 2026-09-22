export async function readDocument(file, ext) {
  const arrayBuffer = await file.arrayBuffer();
  if (ext === 'docx') {
    const { default: mammoth } = await import('mammoth/mammoth.browser.js');
    const { value } = await mammoth.extractRawText({ arrayBuffer });
    return value;
  }
  const pdfjs = await import('pdfjs-dist/build/pdf.mjs');
  const root = new URL('./pdfjs/', import.meta.url).href;
  pdfjs.GlobalWorkerOptions.workerSrc = `${root}pdf.worker.mjs`;
  const loading = pdfjs.getDocument({ data: arrayBuffer, cMapUrl: `${root}cmaps/`, cMapPacked: true, standardFontDataUrl: `${root}standard_fonts/`, wasmUrl: `${root}wasm/`, isEvalSupported: false });
  let pdf;
  try {
    pdf = await loading.promise;
    if (pdf.numPages > 30) throw new Error('Maximal 30 PDF-Seiten / maximum 30 PDF pages.');
    const pages = [];
    for (let i=1; i<=pdf.numPages; i++) {
      const page = await pdf.getPage(i);
      const text = await page.getTextContent();
      let previousY = null, line = '';
      for (const item of text.items) {
        if (!('str' in item)) continue;
        const y = item.transform[5];
        if (previousY !== null && Math.abs(y-previousY)>3) line += '\n';
        line += item.str + (item.hasEOL ? '\n' : ' ');
        previousY = item.hasEOL ? null : y;
      }
      pages.push(line);
    }
    return pages.join('\n\n');
  } finally { await loading.destroy(); }
}
