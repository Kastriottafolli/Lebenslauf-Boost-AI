/* Dropzone + Lebenslauf-Upload (RAG-Index wird serverseitig aufgebaut). */
import * as api from "../api.js";
import { $ } from "../dom.js";
import { t } from "../i18n.js";
import { state } from "../state.js";
import { getKeys } from "./keys.js";
import { updatePhotoThumb } from "./exporter.js";
import { mascotProblem, tourNotify } from "./mascot.js";

export async function uploadCv(file) {
  const status = $("#uploadStatus");
  const dz = $("#dropzone");
  dz.classList.remove("dz-ok");
  status.className = "upload-status";
  status.textContent = t("uploading");
  try {
    const d = await api.uploadCv({
      sessionId: state.sessionId,
      file,
      openaiKey: getKeys().openai,
    });
    state.hasCv = true;
    dz.classList.add("dz-ok");
    status.className = "upload-status ok";
    let msg = t("uploadOk")(d.filename, d.characters, d.rag_mode);
    if (d.photo) {
      state.photo = d.photo;
      updatePhotoThumb();
      msg += " " + t("photoDetected");
    }
    status.textContent = msg;
    tourNotify("cvUploaded");
  } catch (e) {
    status.className = "upload-status err";
    status.textContent = "⚠️ " + e.message;
    mascotProblem("error");
  }
}

export function wireDropzone() {
  const dz = $("#dropzone");
  const fi = $("#fileInput");
  fi.addEventListener("change", () => fi.files[0] && uploadCv(fi.files[0]));
  ["dragover", "dragenter"].forEach((ev) =>
    dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("drag"); }));
  ["dragleave", "drop"].forEach((ev) =>
    dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("drag"); }));
  dz.addEventListener("drop", (e) => { const f = e.dataTransfer.files[0]; if (f) uploadCv(f); });
}
