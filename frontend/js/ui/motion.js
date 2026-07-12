/* Scroll-Reveals, Hero-Spotlight, Konfetti und gestaffelte Einblendungen. */
import { $, $$ } from "../dom.js";

/** Elemente gleiten beim Scrollen gestaffelt ins Bild. */
export function initReveal() {
  const els = document.querySelectorAll(
    ".card, .pstep, .feature, .howto-head, .hero-points li, .step"
  );
  if (!("IntersectionObserver" in window)) {
    els.forEach((el) => el.classList.add("in"));
    return;
  }
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (e.isIntersecting) {
        e.target.classList.add("in");
        io.unobserve(e.target);
      }
    });
  }, { threshold: 0.12, rootMargin: "0px 0px -40px 0px" });

  els.forEach((el, i) => {
    el.classList.add("rv");
    el.style.setProperty("--rvd", `${(i % 8) * 65}ms`);
    io.observe(el);
  });
}

/** Sanfter Lichtschein im Hero folgt der Maus. */
export function initHeroSpotlight() {
  const hero = $("#hero");
  if (!hero) return;
  hero.addEventListener("mousemove", (e) => {
    const r = hero.getBoundingClientRect();
    hero.style.setProperty("--mx", `${((e.clientX - r.left) / r.width) * 100}%`);
    hero.style.setProperty("--my", `${((e.clientY - r.top) / r.height) * 100}%`);
  }, { passive: true });
}

/** Maus-Tilt für 3D-Karten (perspektivische Neigung). */
export function init3DTilt() {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  document.querySelectorAll(".tilt-3d").forEach((el) => {
    // Dezent halten: starke Kippung verschiebt die Fläche unterm Cursor und
    // macht Buttons/Felder schwer klickbar.
    const max = 3;
    el.addEventListener("mousemove", (e) => {
      const r = el.getBoundingClientRect();
      const x = (e.clientX - r.left) / r.width - 0.5;
      const y = (e.clientY - r.top) / r.height - 0.5;
      el.style.transform =
        `perspective(1100px) rotateY(${x * max * 2}deg) rotateX(${-y * max * 2}deg) translateY(-2px)`;
    }, { passive: true });
    el.addEventListener("mouseleave", () => { el.style.transform = ""; });
  });

  const preview = document.querySelector(".preview-card");
  const paper = document.querySelector(".preview-stage .paper");
  if (preview && paper) {
    preview.addEventListener("mousemove", (e) => {
      const r = preview.getBoundingClientRect();
      const x = (e.clientX - r.left) / r.width - 0.5;
      const y = (e.clientY - r.top) / r.height - 0.5;
      paper.style.transform =
        `rotateX(${-y * 4}deg) rotateY(${x * 4}deg) translateY(-3px) translateZ(8px)`;
    }, { passive: true });
    preview.addEventListener("mouseleave", () => {
      paper.style.transform = "rotateX(2deg) rotateY(-1deg)";
    });
  }
}

/** Parallax für den Hintergrund (leichte Maus-Reaktion). */
export function initOrbParallax() {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const backdrop = document.querySelector(".backdrop");
  if (!backdrop) return;
  document.addEventListener("mousemove", (e) => {
    const x = (e.clientX / window.innerWidth - 0.5) * 18;
    const y = (e.clientY / window.innerHeight - 0.5) * 14;
    backdrop.style.transform = `translate3d(${x}px, ${y}px, 0)`;
  }, { passive: true });
}

/** Kurzer Konfetti-Burst (z. B. nach Download). */
export function burstConfetti(count = 48) {
  const wrap = document.createElement("div");
  wrap.className = "confetti";
  const colors = ["#0474c4", "#06457f", "#5379ae", "#262b40", "#a8c4ec", "#2c444c"];
  for (let i = 0; i < count; i += 1) {
    const p = document.createElement("span");
    p.style.setProperty("--x", `${Math.random() * 100}%`);
    p.style.setProperty("--d", `${Math.random() * 0.35}s`);
    p.style.setProperty("--r", `${Math.random() * 720 - 360}deg`);
    p.style.setProperty("--s", `${0.6 + Math.random() * 0.8}`);
    p.style.background = colors[i % colors.length];
    wrap.appendChild(p);
  }
  document.body.appendChild(wrap);
  setTimeout(() => wrap.remove(), 3200);
}

/** Chips nacheinander einblenden. */
export function staggerChips(container) {
  if (!container) return;
  [...container.children].forEach((chip, i) => {
    chip.style.animationDelay = `${i * 55}ms`;
  });
}

/** Vergleichskarten nacheinander einfliegen. */
export function animateCompareCards(bar) {
  if (!bar) return;
  bar.querySelectorAll(".cmp-pick").forEach((card, i) => {
    card.classList.add("cmp-enter");
    card.style.animationDelay = `${i * 120}ms`;
  });
}

/** Primär-Button: kurzer Klick-Ripple. */
export function ripple(e, btn) {
  if (!btn || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const r = document.createElement("span");
  r.className = "ripple";
  const rect = btn.getBoundingClientRect();
  const size = Math.max(rect.width, rect.height);
  r.style.width = r.style.height = `${size}px`;
  r.style.left = `${e.clientX - rect.left - size / 2}px`;
  r.style.top = `${e.clientY - rect.top - size / 2}px`;
  btn.appendChild(r);
  r.addEventListener("animationend", () => r.remove());
}
