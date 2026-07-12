/* Zentraler App-Zustand — eine einzige Quelle der Wahrheit. */
export const state = {
  sessionId: null,
  step: 1,
  content: "",
  provider: "claude",
  results: [],
  design: "modern",
  format: "pdf",
  hasCv: false,
  photo: null,
  serverProviders: {},
};
