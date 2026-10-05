import registry from "../../../static/providers.json" with { type: "json" };
export const PROVIDERS = registry.providers;
export function providerRequest(provider, key, system, messages, options = {}) {
  const config = PROVIDERS.find((p) => p.id === provider);
  if (!config) throw new Error("Unbekannter Anbieter / unknown provider");
  const model = options.model || config.default_model;
  if (!model || !/^[a-zA-Z0-9._:-]{1,100}$/.test(model)) throw new Error("Modell/Deployment pr\xFCfen / check model or deployment");
  let endpoint = config.endpoint;
  const headers = { "Content-Type": "application/json" };
  let body;
  if (provider === "azure") {
    const url = new URL(options.endpoint || "https://invalid.invalid");
    if (url.protocol !== "https:" || !/^[a-z0-9-]+\.(openai\.azure\.com|cognitiveservices\.azure\.com)$/.test(url.hostname) || url.port || url.username || url.password || url.search || url.hash) throw new Error("Azure: https://RESOURCE.openai.azure.com eingeben.");
    endpoint = `${url.origin}/openai/v1/responses`;
  }
  if (config.protocol === "messages") {
    headers["x-api-key"] = key;
    headers["anthropic-version"] = "2023-06-01";
    headers["anthropic-dangerous-direct-browser-access"] = "true";
    body = { model, max_tokens: 1e4, system, messages };
  } else if (config.protocol === "gemini") {
    headers["x-goog-api-key"] = key;
    endpoint += `${encodeURIComponent(model)}:generateContent`;
    body = { systemInstruction: { parts: [{ text: system }] }, contents: messages.map((m) => ({ role: m.role === "assistant" ? "model" : "user", parts: [{ text: m.content }] })), generationConfig: { maxOutputTokens: 1e4 } };
  } else {
    headers.Authorization = `Bearer ${key}`;
    body = { model, input: [{ role: "system", content: system }, ...messages], max_output_tokens: 1e4, store: false };
  }
  return { endpoint, headers, body, model };
}
export function providerText(provider, data) {
  if (data.status === "incomplete" || data.stop_reason === "max_tokens" || data.candidates?.[0]?.finishReason === "MAX_TOKENS") throw new Error("Ausgabe unvollst\xE4ndig / output incomplete. K\xFCrzere Eingabe w\xE4hlen.");
  const content = provider === "claude" ? data.content?.filter((p) => p.type === "text").map((p) => p.text).join("\n") : provider === "gemini" ? data.candidates?.[0]?.content?.parts?.filter((p) => !p.thought).map((p) => p.text || "").join("\n") : data.output?.filter((p) => p.type === "message").flatMap((p) => p.content || []).filter((p) => p.type === "output_text").map((p) => p.text).join("\n");
  if (!content?.trim()) throw new Error("Kein Text erhalten / no text returned. Modellzugriff pr\xFCfen.");
  if (content.length > 1e5) throw new Error("Ausgabe zu lang / output too long.");
  return content.trim().replace(/^```(?:json|markdown)?\s*\n|\n```$/g, "");
}
export async function callProvider(provider, key, system, messages, options = {}) {
  const request = providerRequest(provider, key, system, messages, options);
  const ctrl = new AbortController(), timer = setTimeout(() => ctrl.abort(), 12e4);
  try {
    const response = await fetch(request.endpoint, { method: "POST", headers: request.headers, body: JSON.stringify(request.body), credentials: "omit", referrerPolicy: "no-referrer", signal: ctrl.signal });
    if (!response.ok) throw new Error(`${provider}: ${response.status}. ${response.status === 401 || response.status === 403 ? "API-Key oder Modellzugriff pr\xFCfen / check key or model access." : response.status === 429 ? "Guthaben oder Anfragelimit pr\xFCfen / check credit or rate limit." : "Anbieter-Anfrage fehlgeschlagen / provider request failed."}`);
    return { content: providerText(provider, await response.json()), model: request.model };
  } catch (error) {
    if (error.name === "AbortError") throw new Error("KI-Zeit\xFCberschreitung / AI timeout.");
    if (error instanceof TypeError) throw new Error("Anbieter nicht erreichbar. F\xFCr Browser-Sperren den Serverbetrieb verwenden / provider unreachable; use server mode if browser access is blocked.");
    throw error;
  } finally {
    clearTimeout(timer);
  }
}
