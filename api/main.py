"""FastAPI REST API: POST /analyze — принимает аудиофайл или URL, возвращает анализ звонка.

file и url передаются как поля одной multipart/form-data формы (не альтернативные
Content-Type на одном эндпоинте — FastAPI не может смешивать JSON-body и File в одной
ручке). Переиспользует общий ASR-слой (asr/) и оркестратор агентов (orchestrator.py) —
тот же код, что batch-пайплайн (pipeline.py) и OpenWebUI Pipeline (webui_pipeline.py).
"""
import asyncio
import json
import os
import tempfile

import requests
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect

from agents.coaching import analyze_coaching
from agents.trends import analyze_trends
from asr.diarizer import diarize, operator_talk_ratio
from asr.transcriber import Transcriber
from checklist import checklist_pass_rates, parse_checklist, parse_compliance
from db import get_connection
from orchestrator import analyze as orchestrate_analysis

app = FastAPI(title="Call Center Analytics API")

_transcriber: Transcriber | None = None

SPEAKER_LABELS = {"operator": "Оператор", "client": "Клиент"}


@app.on_event("startup")
async def startup() -> None:
    global _transcriber
    _transcriber = Transcriber(
        os.environ.get("WHISPER_MODEL", "medium"), os.environ.get("WHISPER_LANGUAGE", "ru")
    )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "transcriber_loaded": _transcriber is not None}


async def _run_analysis(audio_path: str) -> dict:
    if _transcriber is None:
        raise HTTPException(status_code=503, detail="Transcriber ещё не инициализирован")

    result = _transcriber.run(audio_path)
    speakers = diarize(audio_path, result["segments"])

    analysis = await orchestrate_analysis(result["transcript_text"])

    transcript = [
        {
            "speaker": SPEAKER_LABELS.get(spk, "Неизвестно"),
            "start": seg["start"],
            "end": seg["end"],
            "text": seg["text"],
        }
        for seg, spk in zip(result["segments"], speakers)
    ]

    return {
        "transcript": transcript,
        "classification": analysis["classification"],
        "quality_score": analysis["quality_score"],
        "compliance": analysis["compliance"],
        "summary": analysis["summary"],
        "action_items": analysis["action_items"],
    }


@app.post("/analyze")
async def analyze_endpoint(
    file: UploadFile | None = File(default=None),
    url: str | None = Form(default=None),
) -> dict:
    if file is None and not url:
        raise HTTPException(status_code=400, detail="Нужен file или url")

    suffix = os.path.splitext(file.filename)[1] if file and file.filename else ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        if file is not None:
            tmp.write(await file.read())
        else:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            tmp.write(resp.content)
        tmp_path = tmp.name

    try:
        return await _run_analysis(tmp_path)
    finally:
        os.unlink(tmp_path)


@app.get("/trends")
async def trends_endpoint(limit: int = 20) -> dict:
    """Бонус: агент трендов по последним `limit` звонкам из Postgres."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT call_topic, call_summary, key_topics FROM call_analysis "
        "ORDER BY analyzed_at DESC LIMIT %s",
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()

    calls = [
        {
            "call_topic": row[0],
            "call_summary": row[1],
            "key_topics": json.loads(row[2]) if row[2] else [],
        }
        for row in rows
    ]
    return await analyze_trends(calls)


@app.get("/coaching/{operator_name}")
async def coaching_endpoint(operator_name: str) -> dict:
    """Рекомендации по обучению для оператора — агрегат по его звонкам + LLM.

    Не переанализирует транскрипты — считает сводку из уже посчитанных
    checklist_json/compliance_json/оценок (см. agents/coaching.py).
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT agent_performance_score, customer_satisfaction, resolution_status, "
        "checklist_json, compliance_json FROM call_analysis WHERE operator_name = %s",
        (operator_name,),
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return {"strengths": [], "weaknesses": [], "recommendations": []}

    scores = [r[0] for r in rows if r[0] is not None]
    satisfactions = [r[1] for r in rows if r[1] is not None]
    resolved = sum(1 for r in rows if r[2] == "resolved")

    checklists = [c for c in (parse_checklist(r[3]) for r in rows) if c]

    issues = []
    for r in rows:
        parsed = parse_compliance(r[4])
        if parsed and not parsed["passed"]:
            issues.extend(parsed["issues"])

    stats = {
        "calls_count": len(rows),
        "avg_agent_score": sum(scores) / len(scores) if scores else None,
        "avg_customer_satisfaction": sum(satisfactions) / len(satisfactions) if satisfactions else None,
        "resolution_rate": resolved / len(rows) * 100 if rows else None,
        "checklist_rates": checklist_pass_rates(checklists) if checklists else {},
        "compliance_issues": sorted(set(issues)),
    }
    return await analyze_coaching(operator_name, stats)


@app.websocket("/transcribe/stream")
async def transcribe_stream(websocket: WebSocket) -> None:
    """Бонус: realtime-транскрибация. Клиент шлёт WAV-чанки ~2-3с бинарными сообщениями,
    сервер транскрибирует каждый чанк независимо (без склейки контекста между чанками —
    осознанный trade-off ради задержки < 3с). Для точного результата на весь файл
    используйте POST /analyze."""
    await websocket.accept()
    if _transcriber is None:
        await websocket.close(code=1011, reason="Transcriber не готов")
        return
    try:
        while True:
            chunk = await websocket.receive_bytes()
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(chunk)
                tmp_path = tmp.name
            try:
                result = await asyncio.to_thread(_transcriber.run, tmp_path)
                await websocket.send_json({"text": result["transcript_text"], "partial": True})
            finally:
                os.unlink(tmp_path)
    except WebSocketDisconnect:
        pass
