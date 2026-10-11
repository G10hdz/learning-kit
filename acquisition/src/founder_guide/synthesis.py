from __future__ import annotations

import os
import re
from typing import Protocol

_CAPTION_PREFIX = re.compile(r"\s*>>\s*")
_BRACKET_TAG = re.compile(r"\[[^\]\[]*\]")
_WHITESPACE = re.compile(r"\s+")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")

_MAX_CHARS = 300
_MAX_SENTENCES = 2
_MAX_DEDUPE_WORDS = 20


def clean_caption_text(text: str) -> str:
    """Strip caption artifacts: '>>' separators, [tags], collapse whitespace."""
    text = _CAPTION_PREFIX.sub(" ", text)
    text = _BRACKET_TAG.sub(" ", text)
    return _WHITESPACE.sub(" ", text).strip()


def _dedupe_repeated(text: str) -> str:
    """Collapse a phrase repeated verbatim in consecutive ASR cues."""
    words = text.split()
    out: list[str] = []
    i = 0
    n = len(words)
    while i < n:
        for k in range(min((n - i) // 2, _MAX_DEDUPE_WORDS), 0, -1):
            if words[i : i + k] == words[i + k : i + 2 * k]:
                out.extend(words[i : i + k])
                i += 2 * k
                break
        else:
            out.append(words[i])
            i += 1
    return " ".join(out)


def truncate_passage(text: str) -> str:
    """Keep ~2 sentences or ~300 chars, whichever is shorter. Sentence-cut."""
    sentences = [s for s in _SENTENCE.split(text) if s.strip()]
    if not sentences:
        return ""
    kept: list[str] = []
    for sentence in sentences:
        if kept and (
            len(kept) >= _MAX_SENTENCES
            or sum(map(len, kept)) + len(sentence) > _MAX_CHARS
        ):
            break
        kept.append(sentence)
    result = " ".join(kept).strip()
    if len(result) <= _MAX_CHARS:
        return result
    cut = result[:_MAX_CHARS].rsplit(" ", 1)[0].strip()
    if cut.endswith((".", "!", "?")):
        return cut
    return cut.rstrip(" ,;:") + "."


class SynthesisError(RuntimeError):
    """Synthesis provider failed; caller should fall through the chain."""


class Synthesizer(Protocol):
    def synthesize(self, question: str, passages: list[tuple[int, str]]) -> str: ...


def _prompt(question: str, passages: list[tuple[int, str]]) -> str:
    body = "\n\n".join(f"[{n}] {text}" for n, text in passages)
    return (
        "Answer in 2-3 sentences, in the same language as the question, "
        "using only these passages. Cite sources inline as [n]. If the "
        "passages do not answer the question, say so in one sentence, in "
        "the same language as the question.\n\n"
        f"Question: {question}\n\n{body}"
    )


class ExtractiveSynthesizer:
    """Deterministic, zero-cost. Cleans and truncates passage texts. Never raises."""

    def synthesize(self, question: str, passages: list[tuple[int, str]]) -> str:
        parts = []
        for _, text in passages:
            cleaned = truncate_passage(_dedupe_repeated(clean_caption_text(text)))
            if not cleaned:
                continue
            parts.append(cleaned)
        return " ".join(parts)


class GeminiSynthesizer:
    """Google Gemini 2.0 Flash via generativelanguage API. Needs GEMINI_API_KEY."""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash") -> None:
        key = api_key.strip()
        if not key:
            raise ValueError("api_key required")
        self._api_key = key
        self._model = model
        self._base_url = (
            "https://generativelanguage.googleapis.com/v1beta/models"
        )
        self._timeout = 30.0

    def synthesize(self, question: str, passages: list[tuple[int, str]]) -> str:
        try:
            import httpx
        except ImportError as error:
            raise SynthesisError("httpx not installed") from error

        url = f"{self._base_url}/{self._model}:generateContent"
        body = {
            "contents": [{"parts": [{"text": _prompt(question, passages)}]}],
            "generationConfig": {"temperature": 0},
        }
        try:
            response = httpx.post(
                url,
                params={"key": self._api_key},
                json=body,
                timeout=self._timeout,
            )
            response.raise_for_status()
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as error:
            raise SynthesisError(str(error)) from error


class DeepSeekSynthesizer:
    """DeepSeek-V3 via OpenAI-compatible API. Needs DEEPSEEK_API_KEY."""

    def __init__(
        self, api_key: str, model: str = "deepseek-chat"
    ) -> None:
        key = api_key.strip()
        if not key:
            raise ValueError("api_key required")
        self._api_key = key
        self._model = model
        self._base_url = "https://api.deepseek.com"
        self._timeout = 30.0

    def synthesize(self, question: str, passages: list[tuple[int, str]]) -> str:
        try:
            import httpx
        except ImportError as error:
            raise SynthesisError("httpx not installed") from error

        body = {
            "model": self._model,
            "messages": [
                {"role": "user", "content": _prompt(question, passages)}
            ],
            "temperature": 0.2,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        try:
            response = httpx.post(
                f"{self._base_url}/chat/completions",
                json=body,
                headers=headers,
                timeout=self._timeout,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as error:
            raise SynthesisError(str(error)) from error


class ChainSynthesizer:
    """Try synthesizers in order. First non-error wins."""

    def __init__(self, synthesizers: list[Synthesizer]) -> None:
        if not synthesizers:
            raise ValueError("synthesizers required")
        self._synthesizers = list(synthesizers)

    def synthesize(self, question: str, passages: list[tuple[int, str]]) -> str:
        last: Exception | None = None
        for synth in self._synthesizers:
            try:
                return synth.synthesize(question, passages)
            except SynthesisError as error:
                last = error
            except Exception as error:
                last = error
        # ExtractiveSynthesizer is always last in default_synthesizer,
        # so this is unreachable there; explicit fallback for custom chains.
        raise SynthesisError(f"all synthesizers failed: {last}")


def default_synthesizer() -> Synthesizer:
    """Wire chain from env vars. Order: DeepSeek -> Gemini -> Extractive.

    ExtractiveSynthesizer is always last and never raises, so synthesis
    degrades gracefully to deterministic when no key is set or APIs fail.
    """
    chain: list[Synthesizer] = []
    deepseek_key = (
        os.environ.get("DEEPSEEK_API_KEY", "").strip()
        or os.environ.get("GUIDE_DEEPSEEK_API_KEY", "").strip()
    )
    if deepseek_key:
        chain.append(DeepSeekSynthesizer(deepseek_key))
    gemini_key = (
        os.environ.get("GEMINI_API_KEY", "").strip()
        or os.environ.get("GUIDE_GEMINI_API_KEY", "").strip()
    )
    if gemini_key:
        chain.append(GeminiSynthesizer(gemini_key))
    chain.append(ExtractiveSynthesizer())
    if len(chain) == 1:
        return chain[0]
    return ChainSynthesizer(chain)


if __name__ == "__main__":
    synth = default_synthesizer()
    passages = [
        (1, "Talk to users before building anything."),
        (2, "Ship a prototype in weeks, not months."),
    ]
    print(synth.synthesize("How to start a startup?", passages))
