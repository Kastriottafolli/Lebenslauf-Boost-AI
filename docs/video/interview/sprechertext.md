# Technical Interview Explainer — Narration

Voice: `en-US-AndrewMultilingualNeural` via edge-tts
Duration target: ~8.1 minutes

1. TITLE — Lebenslauf Boost AI
Hi — thank you for the opportunity to walk you through Lebenslauf Boost AI. This is a full-stack AI engineering project I built to optimize a real résumé against a specific job posting. In this video I'll explain how the frontend and backend work, which external APIs we call and why, how the prompt system is designed, and how the full pipeline runs from upload to export.

2. PITCH — What the product does
At a high level, the product solves a practical hiring problem. Candidates need their résumé rewritten for each job, but unconstrained generative AI often invents skills or achievements. Our design principle is truthfulness first: the model may only use facts from the uploaded CV. We retrieve the most relevant CV sections with RAG, generate one or two drafts with Claude and OpenAI, score them against the job keywords, let the user refine the text, and export a polished PDF or Word file in one of six designs.

3. ARCHITECTURE — System architecture
Architecturally, I kept the system intentionally modular. The frontend is a lightweight vanilla JavaScript SPA — no React build step — styled in a custom Sapphire Nightfall design system, with Boosti, an animated guide that walks users through the flow. The backend is FastAPI with thin routers and thicker services. LLM access goes through a provider abstraction so Claude and OpenAI share the same interface. Prompt text lives outside the code as German and English template files, so prompt engineering can evolve without touching Python. SQLite stores sessions and history. And when keys or embeddings are missing, the app degrades gracefully into a clearly labeled demo mode instead of failing.

4. FRONTEND — Frontend — how the UI works
On the frontend, the experience is a three-step wizard. Step one collects the job description, optional wishes, the CV file, the provider choice — Claude, OpenAI, or compare — and the prompt technique. Step two is the editing surface: the generated markdown, a compare bar when both models run, an ATS keyword panel, and refine chips like shorter or more formal. Step three is design and download with six visual themes. API keys follow a bring-your-own-key model: they live only in localStorage, are attached to each request, and are never persisted server-side. All network calls go through a small api.js module with timeouts on generation.

5. BACKEND — Backend — request path
On the backend, I separated HTTP from business logic. Routers handle sessions, document upload, generation, refine, and export. Services own the real work: file extraction from PDF, DOCX, or text, RAG indexing and retrieval, generation orchestration, and PDF or Word rendering. The LLM package defines an abstract provider, then concrete Anthropic and OpenAI implementations that both return a structured result with content, model name, and demo flag. Pydantic validates every request. A session is the hub: at most one CV document, many generations, and a message history used for refine.

6. APIS — External APIs — what we call and how
We use two different text-generation APIs, which was an explicit project requirement. For Claude, we call Anthropic's Messages API with a system prompt and a message list. For OpenAI, we call Chat Completions with the same logical roles, and separately we use OpenAI embeddings — text-embedding-3-small — to vectorize CV chunks for RAG. Key resolution is important for privacy and demos: a key typed in the UI wins, otherwise we fall back to a server environment key, and if neither exists we return a labeled demo résumé so the full product flow still works. In compare mode, both providers run independently; we do not ask one model to judge the other. Instead we rank drafts with our own ATS keyword overlap score.

7. PROMPTS — Prompt engineering system
The prompt system is one of the parts I'm most intentional about. There are twelve template files under the prompts folder — six logical roles, each in German and English: system role, few-shot examples, chain-of-thought instructions, output format, the user message shell, and refine. Role prompting sets a senior executive résumé writer who must stay factual. Few-shot shows weak versus strong bullets so the model learns impact writing without inventing numbers. Chain-of-thought forces a private seven-step analysis — job requirements, evidence mapping, keyword plan — but those steps are never shown to the user. Format constraints lock the markdown structure. And dynamic context injection fills the user message with the job posting, wishes, and retrieved CV excerpts. When technique is set to auto, we combine few-shot and chain-of-thought in one prompt.

8. PIPELINE — End-to-end generation pipeline
Here is the generation pipeline in order. First, upload extracts text and optionally a photo. Second, we chunk the CV — about seven hundred characters with overlap — and build an index with embeddings when an OpenAI key is available, otherwise pure-Python TF-IDF. Third, at generate time we retrieve the top chunks most relevant to the job description and wishes. Fourth, prompts.py assembles the system persona, the selected technique blocks, the format rules, and the injected RAG context. Fifth, we call one or both providers, run ATS keyword analysis against the job posting, and persist each draft plus the conversation messages for later refine.

9. REFINE_EXPORT — Refine, compare, and export
After the first draft, refine uses conversation history. We send the previous user message, the assistant draft, and a new instruction — for example make it shorter or more technical — then store a new generation with technique refine. Nothing is overwritten, so versions remain auditable. In compare mode the UI highlights the higher ATS score, but the user can pick either draft. Export is intentionally stateless: the client sends the final markdown, design, format, and optional photo. ReportLab and python-docx render six visual themes without writing files into the database.

10. QUALITY — Quality, security, and trade-offs
If I were summarizing engineering judgment for a hiring conversation, I'd highlight four things. Privacy: user keys stay in the browser. Reliability: demo mode means reviewers can exercise the full flow without credentials. Evaluation: we measure fit with an application-specific ATS keyword score, not vague vibes. And maintainability: prompts are data, providers are swappable, routers stay thin. The honest next steps for production would be PostgreSQL with Alembic, real authentication, broader automated tests, and containerized deployment.

11. OUTRO — Thank you
That's the system end to end: a product-shaped AI workflow with clear architecture, two real model providers, a structured prompt stack, retrieval grounding, and a complete user journey from upload to export. Happy to go deeper on any layer — prompts, RAG, or the FastAPI service design. Thank you for watching.
