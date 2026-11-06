"""API tests. The model call is mocked, so these need no API key and spend nothing."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import openai
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # Lets plain `pytest` find the app package.

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.services import llm_service  # noqa: E402
from app.services.knowledge_base import SYSTEM_PROMPT  # noqa: E402
from app.services.language import detect_language, language_instruction  # noqa: E402
from app.services.rate_limiter import limiter  # noqa: E402

client = TestClient(app)

GOOD_ANSWER = {
    "reply": "Sort each material.",
    "parts": [{"label": "Plastic · 플라스틱", "category": "plastic", "item": "Lid", "action": "Rinse it."}],
    "tip": "Local rules differ.",
    "source": "Part A",
}
QUESTION = {"messages": [{"role": "user", "content": "lid"}]}


def completion(content: str) -> SimpleNamespace:
    """The parts of an SDK response that the service reads."""
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, prompt_tokens_details=None),
    )


def api_error(status: int, error_class: type) -> Exception:
    request = httpx.Request("POST", "http://test/chat/completions")
    return error_class("boom", response=httpx.Response(status, request=request), body=None)


@pytest.fixture(autouse=True)
def model(monkeypatch):
    """Replaces the model call and clears the rate limit before every test."""
    limiter.reset()
    create = AsyncMock(return_value=completion(json.dumps(GOOD_ANSWER)))
    monkeypatch.setattr(llm_service.client.chat.completions, "create", create)
    return create


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_page_is_served():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    for path in ("/static/css/style.css", "/static/js/app.js", "/static/js/render.js", "/static/js/api.js"):
        assert client.get(path).status_code == 200


def test_chat_ok():
    response = client.post("/api/chat", json=QUESTION)
    assert response.status_code == 200
    assert response.json() == GOOD_ANSWER


def test_request_sent_to_model(model):
    history = [{"role": "user", "content": str(i) + "x" * 900} for i in range(settings.max_history + 3)]
    client.post("/api/chat", json={"messages": history})

    sent = model.await_args.kwargs
    assert sent["temperature"] == 0.2
    assert sent["response_format"] == {"type": "json_object"}
    assert sent["messages"][0] == {"role": "system", "content": SYSTEM_PROMPT}
    assert SYSTEM_PROMPT.startswith("=== KNOWLEDGE BASE ===\n")
    kept = sent["messages"][1:-1]
    assert len(kept) == settings.max_history
    assert kept[0]["content"].startswith("3x")
    assert all(len(m["content"]) <= settings.max_msg_chars for m in kept)


def test_only_user_messages_are_cut(model):
    answer = json.dumps({**GOOD_ANSWER, "tip": "x" * 2000})
    history = [
        {"role": "user", "content": "q" * 900},
        {"role": "assistant", "content": answer},
        {"role": "user", "content": "lid"},
    ]
    client.post("/api/chat", json={"messages": history})

    kept = model.await_args.kwargs["messages"][1:-1]
    assert len(kept[0]["content"]) == settings.max_msg_chars
    assert kept[1]["content"] == answer  # Stored answers stay valid JSON.


def test_sdk_does_not_retry():
    assert llm_service.client.max_retries == 0


GOOD_JSON = json.dumps(GOOD_ANSWER)
FRIENDLY_ERROR = {"reply": "Sorry, something went wrong. Please try again.", "parts": [], "tip": "", "source": ""}


@pytest.mark.parametrize(
    "raw",
    [
        f"```json\n{GOOD_JSON}\n```",
        f"```\n{GOOD_JSON}\n```",
        f"Here is your answer:\n{GOOD_JSON}\nHope that helps!",
        f'{GOOD_JSON}\n{{"reply": "a second block"}}',
    ],
)
def test_common_issues_are_repaired_without_retry(model, raw):
    model.return_value = completion(raw)
    response = client.post("/api/chat", json=QUESTION)
    assert response.json() == GOOD_ANSWER
    assert model.await_count == 1


@pytest.mark.parametrize("bad", ["not json", '{"reply": "missing keys"}', '{"reply": "broken', "", "[1, 2]"])
def test_invalid_output_is_retried_once(model, bad):
    model.side_effect = [completion(bad), completion(GOOD_JSON)]
    response = client.post("/api/chat", json=QUESTION)
    assert response.json() == GOOD_ANSWER
    assert model.await_count == 2
    first, second = model.await_args_list
    assert first.kwargs == second.kwargs  # The retry is the same request.


@pytest.mark.parametrize("bad", ["not json", '{"reply": "missing keys"}', '{"reply": "broken', ""])
def test_invalid_output_twice_gives_friendly_error_never_raw_text(model, bad):
    model.return_value = completion(bad)
    response = client.post("/api/chat", json={**QUESTION, "lang": "en"})
    assert response.status_code == 200
    assert response.json() == FRIENDLY_ERROR
    assert model.await_count == 2


def test_friendly_error_follows_language(model):
    model.return_value = completion("not json")
    response = client.post("/api/chat", json={**QUESTION, "lang": "ko"})
    assert response.json()["reply"] == "죄송해요, 문제가 생겼어요. 다시 시도해 주세요."


def test_api_error_on_retry_gives_friendly_error(model):
    model.side_effect = [completion("not json"), api_error(500, openai.InternalServerError)]
    response = client.post("/api/chat", json={**QUESTION, "lang": "en"})
    assert response.json() == FRIENDLY_ERROR
    assert model.await_count == 2


def test_api_errors_are_not_retried(model):
    model.side_effect = api_error(500, openai.InternalServerError)
    client.post("/api/chat", json=QUESTION)
    assert model.await_count == 1


@pytest.mark.parametrize(
    ("lang", "expected"),
    [
        ("en", "Too many questions right now — please try again in a minute."),
        ("ko", "지금 질문이 너무 많아요. 1분 뒤에 다시 시도해 주세요."),
    ],
)
def test_api_429_message(model, lang, expected):
    model.side_effect = api_error(429, openai.RateLimitError)
    response = client.post("/api/chat", json={**QUESTION, "lang": lang})
    assert response.status_code == 200
    assert response.json() == {"reply": expected, "parts": [], "tip": "", "source": ""}


def test_other_api_error_message(model):
    model.side_effect = api_error(500, openai.InternalServerError)
    response = client.post("/api/chat", json={**QUESTION, "lang": "en"})
    assert response.status_code == 200
    assert response.json()["reply"] == "Sorry, something went wrong. Please try again."


def test_rate_limit_is_per_ip(model):
    first_ip = {"x-forwarded-for": "1.1.1.1, 9.9.9.9"}
    for _ in range(settings.rate_limit):
        assert client.post("/api/chat", json=QUESTION, headers=first_ip).json()["parts"]

    calls = model.await_count
    blocked = client.post("/api/chat", json=QUESTION, headers=first_ip)
    assert blocked.status_code == 200
    assert blocked.json()["parts"] == []
    assert model.await_count == calls  # Blocked requests never reach the model.

    other_ip = client.post("/api/chat", json=QUESTION, headers={"x-forwarded-for": "2.2.2.2"})
    assert other_ip.json()["parts"]


@pytest.mark.parametrize(
    "body",
    [
        {"messages": []},
        {"messages": [{"role": "system", "content": "x"}]},
        {**QUESTION, "lang": "fr"},
        {**QUESTION, "lang": "ru"},
        {**QUESTION, "lang": "uz"},
    ],
)
def test_invalid_request_is_422(model, body):
    assert client.post("/api/chat", json=body).status_code == 422
    model.assert_not_awaited()


def sent_instruction(model) -> dict:
    return model.await_args.kwargs["messages"][-1]


def ask_auto(text: str, **extra) -> dict:
    return {"messages": [{"role": "user", "content": text}], **extra}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("How do I throw away a pizza box?", "en"),
        ("페트병은 어떻게 버려요?", "ko"),
        ("How do I throw away 종량제봉투?", "ko"),
        ("Как выбросить батарейки?", "en"),  # Other languages fall back to English.
    ],
)
def test_detect_language(text, expected):
    assert detect_language(text) == expected


def test_english_question_gets_english_instruction(model):
    client.post("/api/chat", json=ask_auto("How do I throw away a pizza box?"))
    instruction = sent_instruction(model)
    assert instruction["role"] == "user"
    assert instruction["content"].startswith("Respond ONLY in English.")
    assert "'source' field stays as is" in instruction["content"]
    # Exactly one system message: a second one makes Gemini drop the knowledge base.
    system_messages = [m for m in model.await_args.kwargs["messages"] if m["role"] == "system"]
    assert system_messages == [{"role": "system", "content": SYSTEM_PROMPT}]


def test_korean_question_gets_korean_instruction(model):
    client.post("/api/chat", json=ask_auto("페트병은 어떻게 버려요?"))
    assert sent_instruction(model)["content"] == language_instruction("ko")
    assert sent_instruction(model)["content"].startswith("Respond ONLY in Korean.")


def test_latest_user_message_decides(model):
    history = [
        {"role": "user", "content": "페트병은 어떻게 버려요?"},
        {"role": "assistant", "content": '{"reply": "무색 PET병은 따로 배출해요."}'},
        {"role": "user", "content": "What about the cap?"},
    ]
    client.post("/api/chat", json={"messages": history})
    assert sent_instruction(model)["content"].startswith("Respond ONLY in English.")


def test_korean_button_overrides_english_question(model):
    client.post("/api/chat", json=ask_auto("How do I throw away a pizza box?", lang="ko"))
    assert sent_instruction(model)["content"].startswith("Respond ONLY in Korean.")


def test_english_instruction_keeps_app_name_and_label_format():
    instruction = language_instruction("en")
    assert "내 손안의 분리배출 in Korean letters" in instruction
    assert "(<Korean term>)" in instruction
    assert "no term repeated" in instruction


def test_korean_instruction_uses_korean_labels_only():
    instruction = language_instruction("ko")
    assert "just the Korean term" in instruction
    assert "no repeated term" in instruction


def test_english_button_overrides_korean_question(model):
    client.post("/api/chat", json=ask_auto("페트병은 어떻게 버려요?", lang="en"))
    assert sent_instruction(model)["content"] == language_instruction("en")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("What about the cap?", "Too many questions right now — please try again in a minute."),
        ("페트병은요?", "지금 질문이 너무 많아요. 1분 뒤에 다시 시도해 주세요."),
    ],
)
def test_fixed_replies_follow_detected_language(model, text, expected):
    model.side_effect = api_error(429, openai.RateLimitError)
    assert client.post("/api/chat", json=ask_auto(text)).json()["reply"] == expected


def test_quick_answers_exist_in_both_languages(model):
    response = client.get("/api/quick-answers")
    assert response.status_code == 200
    chips = response.json()["chips"]
    assert [chip["id"] for chip in chips] == ["pet", "food", "vinyl", "batteries", "styrofoam", "pizza"]
    categories = {"plastic", "paper", "papercup", "glass", "can", "vinyl", "styrofoam", "food", "general", "special"}
    for chip in chips:
        assert chip["label"]["en"].isascii() and not chip["label"]["ko"].isascii()
        for lang in ("en", "ko"):
            answer = chip["answer"][lang]
            assert answer["parts"] and answer["source"]
            assert {part["category"] for part in answer["parts"]} <= categories
            assert "내 손안의 분리배출" in answer["tip"]  # The required local-rules line.
        assert detect_language(chip["answer"]["ko"]["reply"]) == "ko"
        for part in chip["answer"]["en"]["parts"]:  # "<English name> (<Korean term>)"
            assert re.fullmatch(r"[^()]*[A-Za-z][^()]* \([^()]*[\uac00-\ud7a3][^()]*\)", part["label"])
        for part in chip["answer"]["ko"]["parts"]:  # Just the Korean term.
            assert "(" not in part["label"] and "·" not in part["label"]
    model.assert_not_awaited()  # Prepared answers never call the model.


def test_empty_base_url_falls_back_to_sdk_default():
    """An empty OPENAI_BASE_URL must not reach the SDK as a blank URL."""
    code = "from app.services.llm_service import client; print(client.base_url)"
    env = {**os.environ, "OPENAI_BASE_URL": "", "OPENAI_API_KEY": "test"}
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True, check=True
    )
    assert "api.openai.com" in result.stdout
