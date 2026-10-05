# Lebenslauf-Designs

Die Auswahl in Schritt 4 aktualisiert die Vorschau ohne erneute KI-Anfrage. Auf schmalen Bildschirmen wird eine geöffnete Textbearbeitung zur Vorschau umgeschaltet, damit die Änderung sichtbar ist. Der Text bleibt erhalten; die Vorschau scrollt weiterhin unabhängig von der Seite.

Die gemeinsamen Vorgaben stehen in `static/document-designs.json`: Akzent, Text-/Trennfarben, lokale Schriftfamilie, Namens-/Abschnittsgrößen und Layoutmerkmale. Browser-Vorschau, Browser-PDF/Word und die Palette des alternativen Serverexports nutzen diese Datei.

| Design | Gestaltung |
|---|---|
| Modern | Petrol, klare Hierarchie, schmale obere Akzentlinie |
| Classic | Noto Serif, zentrierter Lebenslaufkopf, dezente Abschnittslinien |
| Minimal | Einspaltig, dunkle Schrift, reduzierte Dekoration |
| Sapphire | Dunkelblauer Namensbereich, helle Abschnittsflächen |
| Cobalt | Blauer Seitenakzent, helle Abschnittsflächen |
| Slate | Ruhige Grüntöne, obere Linie, großzügiger Kopfbereich |

Noto Sans und Noto Serif sind mit regulären und fetten Schnitten lokal verfügbar und für PDF eingebettet. Die zusätzlichen Fontdateien stammen aus dem offiziellen `notofonts/noto-fonts`-Repository und unterliegen der beigefügten SIL Open Font License (`static/fonts/OFL.txt`). Der Service Worker hält alle vier Schnitte für den Offline-Betrieb vor. Word referenziert die Schriftfamilie; auf Geräten ohne diese Fonts kann Word eine Ersatzschrift verwenden. Die Lesevorschau zeigt den Stil, keine verbindlichen PDF-/Word-Seitenumbrüche.

Projektdateien und im Konto gespeicherte Bewerbungen enthalten die Designkennung. Alte Projekte ohne Kennung öffnen sich mit Modern; unbekannte Kennungen aus lokalen Dateien ebenfalls. Es ist keine Datenbankmigration erforderlich. Die Auswahl verändert keine Qualifikationen und löst keinen kostenpflichtigen KI-Aufruf aus.

Native Projektquellen sind synchronisiert. Android-/iOS-Gerätebuilds sind weiterhin separat zu prüfen.
