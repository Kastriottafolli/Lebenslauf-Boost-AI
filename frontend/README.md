# Frontend

Single-Page-App (Vanilla JS, ES-Module) — wird vom Backend unter `/` ausgeliefert.

```
frontend/
├── index.html          Markup der drei Schritte (Eingabe → Bearbeiten → Export)
├── css/
│   ├── tokens.css      Design-Tokens (Farben, Schrift, Abstände, Radien)
│   ├── base.css        Reset, Typografie, Formulare, Buttons
│   ├── layout.css      Header, Hero, Stepper, Grids, Footer
│   └── components.css  Karten, Dropzone, Chips, Vorschau, Overlay, Toast
└── js/
    ├── main.js         Einstiegspunkt: Init + globale Events
    ├── api.js          Alle HTTP-Aufrufe ans Backend
    ├── state.js        Zentraler App-Zustand
    ├── i18n.js         Zweisprachige Texte (DE/EN)
    └── ui/
        ├── feedback.js Toast + Lade-Overlay
        ├── steps.js    Stepper / Panel-Navigation
        ├── upload.js   Dropzone + Lebenslauf-Upload
        ├── generate.js Generieren, Vergleich, Verfeinern, Keyword-Analyse
        └── exporter.js Design, Foto, Vorschau, Download
```

Typen der API-Objekte: siehe `src/types/api.d.ts`.
