"""Complete document packages grounded in a confirmed profile."""

import json
import re
from pathlib import Path

from fastapi import HTTPException

from backend.llm import llm_service
from backend.services import rag_service

WRITING = json.loads(
    (Path(__file__).resolve().parents[2] / "static/application-writing.json").read_text()
)

DOCUMENTS = ("cv", "cover_letter", "motivation_letter", "email")


def parse_profile(source):
    lines = [line.strip() for line in source.splitlines() if line.strip()]
    email = re.search(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", source, re.IGNORECASE)
    phone = re.search(r"(?:\+\d{1,3}[ ()-]*)?(?:\d[ ()-]*){9,15}", source)
    profile = dict(
        name=re.sub(r"^#+\s*", "", lines[0]) if lines else "",
        email=email.group() if email else "",
        phone=phone.group().strip() if phone else "",
        location="",
        headline="",
        experience="",
        education="",
        skills="",
        languages="",
        source_text=source,
        confirmed=False,
    )
    sections = {
        "experience": r"berufserfahrung|experience|work experience|professional experience|përvoja profesionale|përvojë pune",
        "education": r"ausbildung|education|arsimimi",
        "skills": r"kenntnisse|fähigkeiten|skills|technical skills|aftësitë|njohuritë",
        "languages": r"sprachen|languages|gjuhët",
    }
    current = None
    for line in source.splitlines():
        heading = re.sub(r"^#{1,2}\s*", "", line).strip()
        found = next(
            (
                key
                for key, pattern in sections.items()
                if re.fullmatch(pattern, heading, re.IGNORECASE)
            ),
            None,
        )
        if found:
            current = found
            continue
        if re.match(r"^#{1,2}\s", line):
            current = None
            continue
        if current:
            profile[current] += ("\n" if profile[current] else "") + line
    for key in sections:
        profile[key] = profile[key].strip()
    if len(lines) > 1 and not re.search(r"[@#]|\d{4}", lines[1]) and len(lines[1]) < 120:
        profile["headline"] = lines[1]
    return profile


def system_prompt(language, document="package"):
    locale = WRITING["languages"].get(language, WRITING["languages"]["de"])
    suffix = (
        " Return ONLY JSON with exactly four string fields: cv (complete Markdown resume), cover_letter, motivation_letter, email. No fences."
        if document == "package"
        else f" Return ONLY the complete updated {document} in Markdown."
    )
    return WRITING["prompt"].replace("{language}", locale["language"]) + suffix


def relevant_excerpts(source, description, limit=2):
    terms = set(rag_service.extract_keywords(description, limit=24))
    lines = [
        re.sub(r"^[-*•#]+\s*", "", line).strip()
        for paragraph in source.splitlines()
        for line in re.split(r"(?<=[.!?])\s+(?=[A-ZÄÖÜËÇ])", paragraph)
    ]
    lines = list(
        dict.fromkeys(
            line
            for line in lines
            if 35 <= len(line) <= 400 and not re.search(r"@|https?://", line, re.I)
        )
    )
    ranked = sorted(
        enumerate(lines),
        key=lambda pair: (
            -len(terms.intersection(rag_service.extract_keywords(pair[1], limit=24))),
            pair[0],
        ),
    )
    return [line for _, line in ranked[:limit]]


def demo_package(profile, job, language, wishes=""):
    locale = WRITING["languages"].get(language, WRITING["languages"]["de"])
    source = profile.source_text
    extracted = parse_profile(source)
    for key in ("name", "email", "phone"):
        replacement = getattr(profile, key)
        if replacement and extracted[key] and replacement != extracted[key]:
            source = source.replace(extracted[key], replacement, 1)
    fact_source = "\n".join(
        v for v in (profile.experience, profile.education, profile.skills, source) if v
    )
    facts = relevant_excerpts(fact_source, job.description)
    tasks = relevant_excerpts(job.description, fact_source)
    values = dict(
        name=profile.name or locale["name"],
        role=job.title or locale["role"],
        company=job.company or locale["company"],
        greeting=job.recipient or locale["greeting"],
        fact1=facts[0] if facts else locale["nofact"],
        fact2=facts[1] if len(facts) > 1 else facts[0] if facts else locale["nofact"],
        task1=tasks[0] if tasks else locale["notask"],
        task2=tasks[1] if len(tasks) > 1 else tasks[0] if tasks else locale["notask"],
        personal=wishes.strip() or locale["personal"],
        contact=" · ".join(v for v in (profile.email, profile.phone) if v),
    )
    cv = llm_service._demo_cv({"cv_full": source}, language)
    fields = profile.model_dump(exclude={"source_text", "confirmed"})
    additions = "\n".join(
        f"{key}: {value}"
        for key, value in fields.items()
        if value and key not in ("name", "email", "phone") and value not in source
    )
    if additions:
        cv += "\n\n## " + locale["confirmed"] + "\n" + additions
    return dict(
        cv=cv,
        **{
            key: re.sub(r"\{(\w+)\}", lambda m: values.get(m[1], ""), locale[template]).strip()
            for key, template in (
                ("cover_letter", "cover"),
                ("motivation_letter", "motivation"),
                ("email", "email"),
            )
        },
    )


def build_package(req):
    if not req.profile.confirmed:
        raise HTTPException(422, "Profilangaben zuerst bestätigen / confirm profile first")
    provider = llm_service.get_provider(
        req.provider, req.keys.model_dump() if req.keys else {}, req.model, req.endpoint
    )
    if req.demo:
        documents = demo_package(req.profile, req.job, req.language, req.wishes)
        model = "demo"
    else:
        if not provider.available():
            raise HTTPException(
                422,
                "API-Key fehlt. Demo ausdrücklich auswählen / supply key or select demo.",
            )
        result = provider.generate(
            system_prompt(req.language),
            [
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "confirmed_profile": req.profile.model_dump(),
                            "job": req.job.model_dump(),
                            "preferences": req.wishes,
                        },
                        ensure_ascii=False,
                    ),
                }
            ],
        )
        try:
            documents = json.loads(result.content)
            if not isinstance(documents, dict) or any(
                not isinstance(documents.get(k), str) or not 10 <= len(documents[k]) <= 60000
                for k in DOCUMENTS
            ):
                raise ValueError()
            documents = {k: documents[k] for k in DOCUMENTS}
        except (ValueError, TypeError):
            raise HTTPException(
                502,
                "Unvollständige KI-Bewerbungsmappe / invalid AI application package. Bitte erneut versuchen.",
            ) from None
        model = result.model
    analysis = rag_service.analyze(req.job.description, documents["cv"])
    analysis["checks"] = {
        "placeholders": any(re.search(r"\[[^\]]+\]", documents[k]) for k in DOCUMENTS),
        "short_letters": [
            key
            for key in ("cover_letter", "motivation_letter")
            if len(documents[key].split()) < 120
        ],
        "new_metrics": [
            n
            for n in re.findall(r"\b\d+(?:[.,]\d+)?\s*%", documents["cv"])
            if n not in req.profile.source_text
        ],
    }
    return {
        "documents": documents,
        "analysis": analysis,
        "provider": req.provider,
        "model": model,
        "is_demo": req.demo,
    }
