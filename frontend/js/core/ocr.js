export async function recognizeImage(image, language = "de", progress = () => {
}) {
  const { default: Tesseract } = await import("tesseract.js");
  const { createWorker } = Tesseract;
  const root = new URL("./ocr/", import.meta.url).href;
  const worker = await createWorker(({de:"deu",en:"eng",sq:"sqi"}[language] || "deu"), 1, { workerPath: root + "worker.min.js", corePath: root + "core", langPath: new URL("../../static/ocr/lang", import.meta.url).href, gzip: false, cacheMethod: "none", logger: (message) => progress(message) });
  try {
    const { data } = await worker.recognize(image);
    if (data.text.trim().length < 10) throw new Error("Kein lesbarer Text erkannt / no readable text recognized");
    if (data.text.length > 6e4) throw new Error("Maximal 60.000 Zeichen / max. 60,000 characters");
    return data.text.trim();
  } finally {
    await worker.terminate();
  }
}
