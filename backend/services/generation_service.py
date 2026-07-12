"""Lebenslauf generieren, vergleichen und verfeinern (Kern-Geschäftslogik)."""

import json

from fastapi import HTTPException
from sqlalchemy.orm import Session as DBSession

from backend import schemas
from backend.llm import llm_service, prompts
from backend.models import Generation, Message, Session
from backend.services import rag_service


def generate(db: DBSession, sess: Session, req: schemas.GenerateRequest) -> schemas.GenerateResponse:
    """Erzeugt 1 (Einzelmodus) oder 2 (Vergleichsmodus) Lebenslauf-Versionen."""
    sess.job_description = req.job_description
    sess.wishes = req.wishes or ""
    sess.language = req.language
    keys = req.keys.model_dump() if req.keys else {}

    # ── RAG: relevante Lebenslauf-Auszüge abrufen (Dynamic Context Injection) ──
    cv_full = sess.cv.content if sess.cv else ""
    cv_context = []
    if sess.cv:
        index = rag_service.loads(sess.cv.index_json)
        query = f"{req.job_description}\n{req.wishes or ''}"
        cv_context = rag_service.retrieve(index, query, openai_key=keys.get("openai"))

    system = prompts.system_prompt(req.language)
    user_msg = prompts.build_user_message(
        job_description=req.job_description,
        wishes=req.wishes or "",
        cv_context=cv_context,
        language=req.language,
        technique=req.technique,
    )
    demo_payload = {
        "cv_full": cv_full,
        "job_description": req.job_description,
        "wishes": req.wishes or "",
    }

    providers = ["claude", "openai"] if req.provider == "compare" else [req.provider]

    results = []
    for pname in providers:
        out = llm_service.run_generation(
            pname, system, [{"role": "user", "content": user_msg}],
            language=req.language, demo_payload=demo_payload, keys=keys,
        )
        analysis = rag_service.analyze(req.job_description, out["content"])
        gen = Generation(
            session_id=sess.id,
            provider=out["provider"],
            model=out["model"],
            technique=req.technique,
            content=out["content"],
            ats_score=analysis["ats_score"],
            matched_keywords=json.dumps(analysis["matched_keywords"]),
            missing_keywords=json.dumps(analysis["missing_keywords"]),
        )
        db.add(gen)
        db.flush()
        results.append(
            schemas.GenerationOut(
                generation_id=gen.id,
                provider=out["provider"],
                model=out["model"],
                technique=req.technique,
                content=out["content"],
                analysis=schemas.KeywordAnalysis(**analysis),
                is_demo=out["is_demo"],
            )
        )

    # Conversation History: Prompt + (beste) Antwort speichern.
    db.add(Message(session_id=sess.id, role="user", content=user_msg))

    response = schemas.GenerateResponse(
        mode="compare" if req.provider == "compare" else "single",
        results=results,
    )
    if req.provider == "compare" and len(results) >= 2:
        rec = llm_service.recommend([r.model_dump() for r in results], req.language)
        response.winner_provider = rec["winner_provider"]
        response.recommendation = rec["recommendation"]
        winner = next(r for r in results if r.provider == rec["winner_provider"])
        db.add(Message(session_id=sess.id, role="assistant", content=winner.content))
    else:
        db.add(Message(session_id=sess.id, role="assistant", content=results[0].content))

    db.commit()
    return response


def refine(db: DBSession, sess: Session, req: schemas.RefineRequest) -> schemas.GenerationOut:
    """Verfeinert die letzte Version iterativ (Retaining Conversation History)."""
    history = (
        db.query(Message)
        .filter(Message.session_id == sess.id)
        .order_by(Message.created_at)
        .all()
    )
    last_user = next((m.content for m in reversed(history) if m.role == "user"), "")
    last_assistant = req.current_content or next(
        (m.content for m in reversed(history) if m.role == "assistant"), ""
    )
    if not last_user or not last_assistant:
        raise HTTPException(
            409, "Bitte zuerst einen Lebenslauf generieren / generate a CV first."
        )

    system = prompts.system_prompt(req.language)
    messages = [
        {"role": "user", "content": last_user},
        {"role": "assistant", "content": last_assistant},
        {"role": "user", "content": prompts.refine_message(req.instruction, req.language)},
    ]
    demo_payload = {
        "cv_full": sess.cv.content if sess.cv else last_assistant,
        "job_description": sess.job_description or "",
        "wishes": req.instruction,
    }

    keys = req.keys.model_dump() if req.keys else {}
    out = llm_service.run_generation(
        req.provider, system, messages, language=req.language,
        demo_payload=demo_payload, keys=keys,
    )
    analysis = rag_service.analyze(sess.job_description or req.instruction, out["content"])

    gen = Generation(
        session_id=sess.id, provider=out["provider"], model=out["model"],
        technique="refine", content=out["content"], ats_score=analysis["ats_score"],
        matched_keywords=json.dumps(analysis["matched_keywords"]),
        missing_keywords=json.dumps(analysis["missing_keywords"]),
    )
    db.add(gen)
    db.add(Message(session_id=sess.id, role="user", content=req.instruction))
    db.add(Message(session_id=sess.id, role="assistant", content=out["content"]))
    db.flush()
    gen_id = gen.id
    db.commit()

    return schemas.GenerationOut(
        generation_id=gen_id,
        provider=out["provider"],
        model=out["model"],
        technique="refine",
        content=out["content"],
        analysis=schemas.KeywordAnalysis(**analysis),
        is_demo=out["is_demo"],
    )
