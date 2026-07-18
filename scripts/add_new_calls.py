"""Генерация и загрузка 10 новых синтетических звонков — 5 вымышленных
операторов на отдел (ОО, ОРККиП), каждый со своим call_datetime.

В отличие от pipeline.py (полный DELETE FROM call_analysis + пересчёт ВСЕХ
звонков при каждом запуске), этот скрипт только ДОБАВЛЯЕТ новые записи и не
трогает уже существующие — безопасно перезапускать (пропускает файлы, для
которых аудио или запись в БД уже есть).

Запуск: python scripts/add_new_calls.py
"""
import asyncio
import json
import os
import sys
import time
from datetime import datetime

import edge_tts
import psycopg2
from pydub import AudioSegment

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from asr.diarizer import diarize, operator_talk_ratio
from asr.transcriber import Transcriber, DEFAULT_MODEL, DEFAULT_LANGUAGE
from orchestrator import analyze as orchestrate_analysis
from storage import upload_audio
from db import SCHEMA, _migrate, DATABASE_URL as LOCAL_DATABASE_URL

AUDIO_ROOT = os.path.join(os.path.dirname(__file__), "..", "audio_original_data")
OPERATOR_VOICE = "ru-RU-SvetlanaNeural"
CLIENT_VOICE = "ru-RU-DmitryNeural"
PAUSE_MS = 600

# Публичный (proxy) DATABASE_URL сервиса Postgres на Railway — не хардкодим:
# см. `railway variables --service Postgres --kv` → DATABASE_PUBLIC_URL.
RAILWAY_DATABASE_URL = os.environ.get("RAILWAY_DATABASE_PUBLIC_URL")

CALLS: list[dict] = [
    {
        "department_ru": "ОО", "department_en": "OO",
        "call_topic": "Открытие вклада",
        "operator_name": "Иванова Мария Сергеевна",
        "call_datetime": datetime(2026, 6, 30, 10, 15),
        "turns": [
            ("operator", "Добрый день, банк, меня зовут Мария Сергеевна, чем могу помочь?"),
            ("client", "Здравствуйте, хочу открыть вклад, подскажите какие есть варианты."),
            ("operator", "Конечно! У нас есть срочный вклад под двенадцать процентов годовых и накопительный счёт с пополнением. Какая сумма и на какой срок вас интересует?"),
            ("client", "Хочу положить сто тысяч рублей примерно на полгода."),
            ("operator", "Тогда лучше всего подойдёт срочный вклад на шесть месяцев, ставка двенадцать целых пять десятых процента. Проценты можно получать ежемесячно или в конце срока."),
            ("client", "А если мне понадобятся деньги раньше срока?"),
            ("operator", "При досрочном расторжении ставка будет пересчитана по вкладу до востребования, это стоит учитывать."),
            ("client", "Понятно, тогда открою на полгода, деньги вроде не понадобятся."),
            ("operator", "Отлично, оформить вклад можно прямо в мобильном приложении за пару минут, либо я запишу вас в отделение."),
            ("client", "Давайте я попробую через приложение."),
            ("operator", "Хорошо, если возникнут сложности — звоните, поможем. Хорошего дня!"),
            ("client", "Спасибо большое, до свидания!"),
        ],
    },
    {
        "department_ru": "ОО", "department_en": "OO",
        "call_topic": "Смс-информирование",
        "operator_name": "Петров Алексей Николаевич",
        "call_datetime": datetime(2026, 7, 2, 14, 40),
        "turns": [
            ("operator", "Добрый день, банк, меня зовут Алексей Николаевич, слушаю вас."),
            ("client", "Здравствуйте, у меня перестали приходить смс о списаниях с карты."),
            ("operator", "Понимаю, давайте проверим. Подскажите, пожалуйста, номер телефона, привязанный к карте."),
            ("client", "Плюс триста семьдесят пять двадцать девять пятьсот двенадцать."),
            ("operator", "Вижу, услуга смс-информирования подключена, но по счёту накопилась задолженность за неё, поэтому оповещения приостановлены."),
            ("client", "Ой, я не знал, что это платная услуга, думал бесплатно."),
            ("operator", "Да, стоимость два рубля в месяц, спишется автоматически при следующем поступлении средств."),
            ("client", "Хорошо, а как быстро восстановится отправка смс?"),
            ("operator", "Как только спишется задолженность — в течение суток. Либо можем подключить push-уведомления в приложении бесплатно."),
            ("client", "О, давайте лучше push, чтобы не платить."),
            ("operator", "Отлично, подключил push-уведомления, услугу смс отключу. Что-то ещё?"),
            ("client", "Нет, спасибо, всё понятно!"),
        ],
    },
    {
        "department_ru": "ОО", "department_en": "OO",
        "call_topic": "Потеря карты",
        "operator_name": "Соколова Екатерина Викторовна",
        "call_datetime": datetime(2026, 7, 7, 9, 5),
        "turns": [
            ("operator", "Добрый вечер, банк, меня зовут Екатерина Викторовна, чем могу помочь?"),
            ("client", "Здравствуйте, я потеряла карту заграницей, очень переживаю!"),
            ("operator", "Не переживайте, сейчас всё решим. Для начала я заблокирую карту, чтобы ей никто не смог воспользоваться."),
            ("client", "Да, пожалуйста, заблокируйте скорее!"),
            ("operator", "Готово, карта заблокирована. Подскажите, деньги на счету нужны прямо сейчас?"),
            ("client", "Да, у меня почти нет наличных, я в чужой стране."),
            ("operator", "Понимаю. Могу оформить срочный перевыпуск карты в отделении по возвращении, а пока предложу вам получить деньги через партнёрскую систему переводов."),
            ("client", "К сожалению, местного счёта у меня нет."),
            ("operator", "Ничего, деньги можно забрать наличными по паспорту в отделении партнёра, инструкция придёт вам на почту."),
            ("client", "Это было бы отлично, спасибо!"),
            ("operator", "Оформляю, инструкция придёт в течение пяти минут. Берегите себя!"),
            ("client", "Спасибо огромное за помощь, до свидания."),
        ],
    },
    {
        "department_ru": "ОО", "department_en": "OO",
        "call_topic": "Досрочное погашение",
        "operator_name": "Кузнецов Дмитрий Олегович",
        "call_datetime": datetime(2026, 7, 10, 16, 20),
        "turns": [
            ("operator", "Добрый день, банк, меня зовут Дмитрий Олегович, слушаю вас."),
            ("client", "Здравствуйте, хочу досрочно погасить кредит, подскажите, как это сделать."),
            ("operator", "Конечно, подскажите номер договора, чтобы найти кредит."),
            ("client", "Договор номер пятьсот сорок два дробь двадцать три."),
            ("operator", "Нашёл, остаток задолженности сто двадцать три тысячи рублей. Хотите погасить полностью или частично?"),
            ("client", "Полностью, есть возможность закрыть сейчас."),
            ("operator", "Отлично, для полного досрочного погашения нужно подать заявление за один день до желаемой даты платежа — через приложение или в отделении."),
            ("client", "А комиссия за досрочное погашение есть?"),
            ("operator", "Нет, комиссий и штрафов нет, это ваше законное право в любой момент."),
            ("client", "Хорошо, тогда подам заявку через приложение сегодня."),
            ("operator", "Отлично, после подачи заявки просто внесите нужную сумму на счёт до указанной даты, и кредит закроется автоматически."),
            ("client", "Понял, спасибо большое за помощь!"),
        ],
    },
    {
        "department_ru": "ОО", "department_en": "OO",
        "call_topic": "Сбой приложения",
        "operator_name": "Волкова Наталья Игоревна",
        "call_datetime": datetime(2026, 7, 15, 11, 50),
        "turns": [
            ("operator", "Добрый день, банк, меня зовут Наталья Игоревна, чем могу помочь?"),
            ("client", "Здравствуйте, не могу зайти в мобильное приложение, выдаёт ошибку."),
            ("operator", "Подскажите, пожалуйста, какая именно ошибка появляется на экране?"),
            ("client", "Пишет \"неверный логин или пароль\", хотя я точно всё правильно ввожу."),
            ("operator", "Возможно, был превышен лимит попыток входа и аккаунт временно заблокирован. Проверю по вашему номеру телефона."),
            ("client", "Да, конечно, номер плюс триста семьдесят пять сорок четыре триста двенадцать."),
            ("operator", "Действительно, вход заблокирован после нескольких неудачных попыток. Сейчас разблокирую, попробуйте зайти заново через пару минут."),
            ("client", "Хорошо, а пароль менять не нужно?"),
            ("operator", "Не обязательно, но если снова не получится войти — лучше сбросить пароль через смс-код на этой же странице."),
            ("client", "Понял, попробую, спасибо."),
            ("operator", "Пожалуйста, если ошибка повторится — звоните, разберёмся. Хорошего дня!"),
            ("client", "Спасибо, до свидания!"),
        ],
    },
    {
        "department_ru": "ОРККиП", "department_en": "ORKKiP",
        "call_topic": "Открытие расчётного счёта",
        "operator_name": "Морозова Ольга Павловна",
        "call_datetime": datetime(2026, 7, 1, 12, 30),
        "turns": [
            ("operator", "Добрый день, банк, меня зовут Ольга Павловна, чем могу помочь?"),
            ("client", "Здравствуйте, хочу открыть расчётный счёт для нового ИП."),
            ("operator", "Отлично, подскажите, ИП уже зарегистрировано в налоговой?"),
            ("client", "Да, документы уже на руках, ОГРНИП есть."),
            ("operator", "Хорошо, тогда для открытия счёта потребуется паспорт, ОГРНИП и заявление, которое можно заполнить у нас в отделении или онлайн."),
            ("client", "А сколько по времени занимает открытие счёта?"),
            ("operator", "Обычно один рабочий день, при онлайн-заявке счёт может быть готов уже через пару часов."),
            ("client", "Отлично, а обслуживание счёта платное?"),
            ("operator", "Первые три месяца обслуживание бесплатное, далее по тарифу для ИП — от нуля рублей при определённом обороте."),
            ("client", "Хорошо, тогда оформлю онлайн-заявку сегодня же."),
            ("operator", "Прекрасно, отправлю вам ссылку на форму на почту. Если появятся вопросы — обращайтесь."),
            ("client", "Спасибо большое, до свидания!"),
        ],
    },
    {
        "department_ru": "ОРККиП", "department_en": "ORKKiP",
        "call_topic": "Зарплатный проект",
        "operator_name": "Сидоров Виктор Андреевич",
        "call_datetime": datetime(2026, 7, 3, 15, 10),
        "turns": [
            ("operator", "Добрый день, банк, меня зовут Виктор Андреевич, слушаю вас."),
            ("client", "Здравствуйте, наша компания хочет подключить зарплатный проект для сотрудников."),
            ("operator", "Отлично, подскажите, сколько примерно сотрудников в компании?"),
            ("client", "Около тридцати человек."),
            ("operator", "Для такого количества у нас действуют специальные условия — бесплатный выпуск карт и льготные условия по кредитам для сотрудников."),
            ("client", "Звучит интересно, а как долго занимает подключение?"),
            ("operator", "После подписания договора и передачи реестра сотрудников — обычно пять-семь рабочих дней на выпуск карт."),
            ("client", "Хорошо, а что нужно от нас для начала оформления?"),
            ("operator", "Реквизиты компании, список сотрудников с паспортными данными и подписанный договор — я вышлю шаблон вам на почту."),
            ("client", "Отлично, ждём документы, спасибо!"),
            ("operator", "Направлю всё в течение часа. Если будут вопросы по заполнению — звоните."),
            ("client", "Хорошо, спасибо большое, до свидания!"),
        ],
    },
    {
        "department_ru": "ОРККиП", "department_en": "ORKKiP",
        "call_topic": "Блокировка счёта",
        "operator_name": "Лебедева Анна Дмитриевна",
        "call_datetime": datetime(2026, 7, 9, 10, 45),
        "turns": [
            ("operator", "Добрый день, банк, меня зовут Анна Дмитриевна, чем могу помочь?"),
            ("client", "Здравствуйте, у нашей компании заблокирован расчётный счёт, не могу понять почему."),
            ("operator", "Сейчас проверю. Подскажите, пожалуйста, название компании или ИНН."),
            ("client", "ИНН семь семь ноль ноль сто двадцать три четыреста пятьдесят шесть."),
            ("operator", "Вижу, счёт приостановлен в рамках проверки операции службой финансового мониторинга — была крупная нетипичная транзакция."),
            ("client", "Это была обычная оплата поставщику, ничего подозрительного!"),
            ("operator", "Понимаю, для снятия блокировки потребуется предоставить подтверждающие документы по этой операции — договор и накладные."),
            ("client", "Хорошо, а как долго рассматривается такая проверка?"),
            ("operator", "Обычно от одного до трёх рабочих дней после получения полного пакета документов."),
            ("client", "Понял, отправим документы сегодня же."),
            ("operator", "Отлично, направьте их через форму обратной связи в интернет-банке с пометкой \"для комплаенс\". Как только получим — ускорим проверку."),
            ("client", "Спасибо за разъяснение, отправим сегодня."),
        ],
    },
    {
        "department_ru": "ОРККиП", "department_en": "ORKKiP",
        "call_topic": "Увеличение овердрафта",
        "operator_name": "Козлов Сергей Викторович",
        "call_datetime": datetime(2026, 7, 13, 13, 25),
        "turns": [
            ("operator", "Добрый день, банк, меня зовут Сергей Викторович, слушаю вас."),
            ("client", "Здравствуйте, хотим увеличить лимит овердрафта по расчётному счёту."),
            ("operator", "Хорошо, подскажите, какой лимит у вас сейчас и до какой суммы хотите увеличить?"),
            ("client", "Сейчас пятьсот тысяч, хотим до полутора миллионов."),
            ("operator", "Понял, для увеличения лимита потребуется предоставить финансовую отчётность за последние два квартала и подтверждение оборотов по счёту."),
            ("client", "Отчётность есть, можем отправить хоть сегодня."),
            ("operator", "Отлично, после получения документов решение обычно принимается в течение трёх-пяти рабочих дней."),
            ("client", "А есть гарантия, что лимит точно увеличат?"),
            ("operator", "Гарантии дать не могу, решение принимает кредитный комитет на основе финансовых показателей, но при стабильных оборотах шансы высокие."),
            ("client", "Понятно, тогда отправим документы и будем ждать решения."),
            ("operator", "Хорошо, направьте, пожалуйста, документы через личный кабинет, раздел \"Кредитование\". Я буду отслеживать заявку."),
            ("client", "Спасибо, отправим сегодня же."),
        ],
    },
    {
        "department_ru": "ОРККиП", "department_en": "ORKKiP",
        "call_topic": "Ошибка в выписке",
        "operator_name": "Новикова Татьяна Романовна",
        "call_datetime": datetime(2026, 7, 16, 17, 5),
        "turns": [
            ("operator", "Добрый день, банк, меня зовут Татьяна Романовна, чем могу помочь?"),
            ("client", "Здравствуйте, в выписке по счёту вижу платёж, которого мы не делали."),
            ("operator", "Давайте разберёмся, подскажите, пожалуйста, дату и сумму операции."),
            ("client", "Пятнадцатого числа, сумма двадцать три тысячи рублей, назначение не указано."),
            ("operator", "Сейчас проверю по системе... вижу операцию, это была комиссия за обслуживание эквайринга за прошлый месяц, просто в выписке не указано развёрнутое назначение."),
            ("client", "А почему сумма больше обычного, раньше комиссия была меньше?"),
            ("operator", "Похоже, вырос оборот по эквайрингу, отсюда и комиссия немного выше, это стандартный процент от оборота."),
            ("client", "Понятно, а можно получить детальную расшифровку по этой комиссии?"),
            ("operator", "Конечно, направлю вам подробный расчёт на электронную почту в течение часа."),
            ("client", "Отлично, буду ждать, спасибо за разъяснение!"),
            ("operator", "Пожалуйста, если появятся ещё вопросы по выписке — обращайтесь."),
            ("client", "Обязательно, до свидания!"),
        ],
    },
]


async def _synth_turn(text: str, voice: str, path: str) -> None:
    await edge_tts.Communicate(text, voice).save(path)


async def synth_call(call: dict) -> str:
    """Возвращает путь к .wav, генерируя его через edge-tts, если ещё нет."""
    dept_dir = os.path.join(AUDIO_ROOT, call["department_ru"])
    os.makedirs(dept_dir, exist_ok=True)
    wav_path = os.path.join(dept_dir, f"{call['call_topic']}.wav")
    if os.path.exists(wav_path):
        print(f"  [пропуск] {call['call_topic']}: аудио уже есть")
        return wav_path

    tmp_dir = os.path.join(dept_dir, f".tmp_{call['call_topic']}")
    os.makedirs(tmp_dir, exist_ok=True)
    audio = AudioSegment.silent(duration=0)
    pause = AudioSegment.silent(duration=PAUSE_MS)
    for i, (speaker, text) in enumerate(call["turns"]):
        voice = OPERATOR_VOICE if speaker == "operator" else CLIENT_VOICE
        turn_path = os.path.join(tmp_dir, f"{i:02d}_{speaker}.mp3")
        await _synth_turn(text, voice, turn_path)
        audio += AudioSegment.from_file(turn_path) + pause

    audio.export(wav_path, format="wav")
    for f in os.listdir(tmp_dir):
        os.remove(os.path.join(tmp_dir, f))
    os.rmdir(tmp_dir)
    print(f"  синтез: {call['call_topic']} ({audio.duration_seconds:.1f}с) → {wav_path}")
    return wav_path


def call_already_in_db(file_name: str) -> bool:
    conn = psycopg2.connect(LOCAL_DATABASE_URL)
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM call_analysis WHERE file_name = %s", (file_name,))
        exists = cur.fetchone() is not None
    conn.close()
    return exists


def process_call(transcriber: Transcriber, call: dict, wav_path: str) -> dict:
    print(f"  [{call['department_en']}] {call['call_topic']} — транскрипция...", end=" ", flush=True)
    t0 = time.time()
    result = transcriber.run(wav_path)
    print(f"{result['duration_sec']:.0f}с аудио → {time.time() - t0:.0f}с")

    speakers = diarize(wav_path, result["segments"])
    op_ratio = operator_talk_ratio(result["segments"], speakers)

    print("    анализ (4 агента)...", end=" ", flush=True)
    t0 = time.time()
    analysis = asyncio.run(orchestrate_analysis(result["transcript_text"]))
    print(f"{time.time() - t0:.0f}с")

    audio_key = upload_audio(wav_path, f"{call['department_ru']}/{call['call_topic']}.wav")

    return {
        "file_name": f"{call['call_topic']}.wav",
        "department": call["department_en"],
        "call_topic": call["call_topic"],
        "operator_name": call["operator_name"],
        "call_datetime": call["call_datetime"],
        "audio_key": audio_key,
        "speakers": speakers,
        "operator_talk_ratio": op_ratio,
        **result,
        "call_type": analysis["classification"]["topic"],
        "urgency": analysis["classification"]["priority"],
        "customer_intent": analysis["customer_intent"],
        "resolution_status": analysis["resolution_status"],
        "customer_satisfaction_score": analysis["customer_satisfaction_score"],
        "escalation_flag": analysis["escalation_flag"],
        "key_topics": analysis["key_topics"],
        "call_summary": analysis["summary"],
        "checklist": analysis["quality_score"]["checklist"],
        "agent_performance_score": analysis["quality_score"]["total"] / 10,
        "compliance": analysis["compliance"],
        "action_items": analysis["action_items"],
    }


def insert_records(records: list[dict], database_url: str, label: str) -> None:
    conn = psycopg2.connect(database_url)
    with conn.cursor() as cur:
        cur.execute(SCHEMA)
    conn.commit()
    _migrate(conn)

    inserted = 0
    with conn.cursor() as cur:
        for r in records:
            cur.execute("SELECT 1 FROM call_analysis WHERE file_name = %s", (r["file_name"],))
            if cur.fetchone() is not None:
                print(f"  [{label}] пропуск {r['file_name']}: уже в базе")
                continue

            cur.execute(
                """INSERT INTO ai_transcribed_calls
                   (file_name, department, call_topic, transcript_text, detected_language, duration_sec)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (r["file_name"], r["department"], r["call_topic"], r["transcript_text"],
                 r["detected_language"], r["duration_sec"]),
            )
            cur.execute(
                """INSERT INTO call_analysis
                   (file_name, department, call_topic, transcript_text, call_summary,
                    sentiment_score, sentiment_label, call_type, customer_intent, urgency,
                    resolution_status, agent_performance_score, customer_satisfaction,
                    escalation_flag, key_topics, silence_sec, silence_pct, pause_count,
                    operator_talk_ratio, checklist_json, compliance_json, action_items_json,
                    audio_key, operator_name, call_datetime)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    r["file_name"], r["department"], r["call_topic"], r["transcript_text"],
                    r.get("call_summary", ""), None, r.get("urgency", ""), r.get("call_type", ""),
                    r.get("customer_intent", ""), r.get("urgency", ""), r.get("resolution_status", ""),
                    r.get("agent_performance_score"), r.get("customer_satisfaction_score"),
                    int(bool(r.get("escalation_flag", False))),
                    json.dumps(r.get("key_topics", []), ensure_ascii=False),
                    r.get("silence_sec"), r.get("silence_pct"), r.get("pause_count"),
                    r.get("operator_talk_ratio"),
                    json.dumps(r.get("checklist", {}), ensure_ascii=False),
                    json.dumps(r.get("compliance", {}), ensure_ascii=False),
                    json.dumps(r.get("action_items", []), ensure_ascii=False),
                    r.get("audio_key"), r.get("operator_name"), r.get("call_datetime"),
                ),
            )
            for i, (seg, spk) in enumerate(zip(r.get("segments", []), r.get("speakers", []))):
                cur.execute(
                    """INSERT INTO call_segments (file_name, seg_index, start_sec, end_sec, speaker, text)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (r["file_name"], i, seg["start"], seg["end"], spk, seg["text"]),
                )
            inserted += 1
    conn.commit()
    conn.close()
    print(f"  [{label}] Добавлено новых звонков: {inserted}")


def main() -> None:
    print(f"Обрабатываю {len(CALLS)} новых синтетических звонков...\n")

    to_process = [c for c in CALLS if not call_already_in_db(f"{c['call_topic']}.wav")]
    if not to_process:
        print("Все звонки уже загружены в локальную базу — нечего делать.")
        return

    print(f"[1/3] Синтез аудио (edge-tts) для {len(to_process)} звонков...")
    for call in to_process:
        asyncio.run(synth_call(call))
    print()

    print(f"[2/3] Транскрипция + диаризация + анализ (Whisper {DEFAULT_MODEL})...")
    transcriber = Transcriber(DEFAULT_MODEL, DEFAULT_LANGUAGE)
    records = []
    for call in to_process:
        wav_path = os.path.join(AUDIO_ROOT, call["department_ru"], f"{call['call_topic']}.wav")
        records.append(process_call(transcriber, call, wav_path))
    del transcriber
    print()

    cache_path = os.path.join(os.path.dirname(__file__), "..", "new_calls_cache.json")
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(
            [{**r, "call_datetime": r["call_datetime"].isoformat()} for r in records],
            f, ensure_ascii=False, indent=2,
        )
    print(f"Кэш сохранён: {cache_path}\n")

    print("[3/3] Загрузка в PostgreSQL (локальная + Railway)...")
    insert_records(records, LOCAL_DATABASE_URL, "локальная БД")
    if RAILWAY_DATABASE_URL:
        insert_records(records, RAILWAY_DATABASE_URL, "Railway БД")
    else:
        print("  RAILWAY_DATABASE_PUBLIC_URL не задан — Railway пропущен "
              "(см. `railway variables --service Postgres --kv`)")

    print("\nГотово.")


if __name__ == "__main__":
    main()
