/* Stepper-Navigation mit weichen Panel-Übergängen. */
import { $, $$ } from "../dom.js";
import { state } from "../state.js";
import { mascotOnStep } from "./mascot.js";

export function goStep(n) {
  const prev = state.step;
  state.step = n;

  const hero = $("#hero");
  if (hero) hero.style.display = n === 1 ? "" : "none";

  $$(".panel").forEach((p) => {
    const isTarget = p.id === `panel-${n}`;
    if (p.classList.contains("active") && !isTarget) {
      p.classList.add("leaving");
      p.classList.remove("active");
      setTimeout(() => p.classList.remove("leaving"), 420);
    } else if (isTarget) {
      p.classList.add("active", "entering");
      setTimeout(() => p.classList.remove("entering"), 520);
    }
  });

  $$(".step").forEach((s) => {
    const sn = Number(s.dataset.step);
    s.classList.toggle("active", sn === n);
    s.classList.toggle("done", sn < n);
  });

  if (prev !== n) window.scrollTo({ top: 0, behavior: "smooth" });
  mascotOnStep(n);
}
