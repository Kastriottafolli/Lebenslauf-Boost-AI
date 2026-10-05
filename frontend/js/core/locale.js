import albanian from "../../../static/albanian.json" with { type: "json" };
export const LANGUAGES = ["de", "en", "sq"];
export function translate(language, de, en, sq) {return language === "sq" ? (sq ?? albanian[de] ?? de) : language === "en" ? en : de;}
