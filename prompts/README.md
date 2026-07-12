# Prompts

Alle Prompt-Vorlagen der App als einfache Textdateien — getrennt vom Code,
damit sie leicht zu lesen und anzupassen sind.

Geladen werden sie von `backend/llm/prompts.py` (Loader mit Cache).

| Datei | Zweck | Technik |
| --- | --- | --- |
| `system_{de,en}.txt` | System-Persona (Karriere-Coach / HR-Profi) | Role Prompting |
| `few_shot_{de,en}.txt` | Vorher/Nachher-Beispiele für starke Bulletpoints | Few-shot Prompting |
| `chain_of_thought_{de,en}.txt` | Strukturiertes internes Vorgehen vor dem Schreiben | Chain-of-Thought |
| `format_{de,en}.txt` | Verbindliches Markdown-Ausgabeformat + Regeln | Output Constraints |
| `user_message_{de,en}.txt` | Haupt-Prompt mit Platzhaltern (`{job_description}`, `{wishes}`, `{cv_context}`, `{technique_block}`, `{format}`) | Dynamic Context Injection |
| `refine_{de,en}.txt` | Folge-Nachricht für iteratives Verfeinern (`{instruction}`, `{format}`) | Conversation History |
