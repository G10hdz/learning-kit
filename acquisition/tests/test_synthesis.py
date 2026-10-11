import unittest
from unittest import mock

from founder_guide.synthesis import (
    ChainSynthesizer,
    DeepSeekSynthesizer,
    ExtractiveSynthesizer,
    GeminiSynthesizer,
    SynthesisError,
    _prompt,
    clean_caption_text,
    default_synthesizer,
    truncate_passage,
)


class PromptTests(unittest.TestCase):
    def test_prompt_asks_to_reply_in_the_question_language(self) -> None:
        prompt = _prompt("¿Cómo validar con usuarios?", [(1, "Habla con usuarios.")])
        self.assertIn("same language as the question", prompt)
        self.assertIn("2-3 sentences", prompt)

    def test_prompt_keeps_inline_citation_format(self) -> None:
        prompt = _prompt("¿Qué hacer?", [(1, "Primera fuente."), (2, "Segunda.")])
        self.assertIn("[1] Primera fuente.", prompt)
        self.assertIn("[2] Segunda.", prompt)
        self.assertIn("Cite sources inline as [n]", prompt)
        self.assertIn("Question: ¿Qué hacer?", prompt)


class CleanCaptionTextTests(unittest.TestCase):
    def test_strips_speaker_markers_and_tags(self) -> None:
        text = ">> Orador: bien [laughter] sigamos >> >> siguiente [Music]"
        self.assertEqual(
            clean_caption_text(text),
            "Orador: bien sigamos siguiente",
        )

    def test_collapses_whitespace(self) -> None:
        self.assertEqual(clean_caption_text("a\n\n  b\t c  "), "a b c")

    def test_tag_inside_text_keeps_word_boundary(self) -> None:
        self.assertEqual(clean_caption_text("hola[applause]mundo"), "hola mundo")


class DedupeTests(unittest.TestCase):
    def test_removes_verbatim_asr_repetition(self) -> None:
        synth = ExtractiveSynthesizer()
        out = synth.synthesize(
            "q", [(1, "talk to users talk to users before building.")]
        )
        self.assertEqual(out, "talk to users before building.")


class TruncatePassageTests(unittest.TestCase):
    def test_keeps_first_two_sentences(self) -> None:
        text = (
            "First sentence here. Second sentence too. "
            "Third sentence dropped. Fourth also."
        )
        self.assertEqual(
            truncate_passage(text),
            "First sentence here. Second sentence too.",
        )

    def test_keeps_short_passage_whole(self) -> None:
        self.assertEqual(
            truncate_passage("Only one short sentence."),
            "Only one short sentence.",
        )

    def test_hard_cuts_long_sentence(self) -> None:
        result = truncate_passage("a" * 400 + " more.")
        self.assertLessEqual(len(result), 301)
        self.assertTrue(result.endswith("."))


class SynthesizeTests(unittest.TestCase):
    def test_empty_passage_is_dropped(self) -> None:
        synth = ExtractiveSynthesizer()
        out = synth.synthesize(
            "q",
            [
                (1, "[music]"),
                (2, "Real content here."),
                (3, ">>  "),
            ],
        )
        self.assertEqual(out, "Real content here.")

    def test_never_raises_on_dirty_input(self) -> None:
        synth = ExtractiveSynthesizer()
        dirty = [
            (1, ">> [laughter] blabla >> [Music] y seguimos"),
            (2, "repetir repetir"),
            (3, ""),
            (4, "[applause]"),
            (5, "x" * 5000),
            (6, "   "),
            (7, ">>\n>>\t>>"),
        ]
        out = synth.synthesize("¿alguna pregunta?", dirty)
        self.assertIsInstance(out, str)
        self.assertNotIn("[", out)
        self.assertNotIn(">>", out)


class DeepSeekSynthesizerTests(unittest.TestCase):
    def _response(self, json_data, status=200):
        response = mock.Mock()
        response.status_code = status
        response.json.return_value = json_data
        if status >= 400:
            response.raise_for_status.side_effect = (
                __import__("httpx").HTTPStatusError(
                    "boom", request=mock.Mock(), response=response
                )
            )
        return response

    def test_ok_returns_content(self) -> None:
        synth = DeepSeekSynthesizer("dsk-key")
        response = self._response(
            {"choices": [{"message": {"content": "  Hi there  "}}]}
        )
        with mock.patch("httpx.post", return_value=response) as post:
            out = synth.synthesize("q", [(1, "p")])
        self.assertEqual(out, "Hi there")
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["model"], "deepseek-chat")
        self.assertEqual(body["temperature"], 0.2)
        self.assertEqual(body["messages"][0]["role"], "user")
        self.assertEqual(
            post.call_args.kwargs["headers"]["Authorization"],
            "Bearer dsk-key",
        )

    def test_http_500_raises_synthesis_error(self) -> None:
        synth = DeepSeekSynthesizer("dsk-key")
        with mock.patch("httpx.post", return_value=self._response({}, 500)):
            with self.assertRaises(SynthesisError):
                synth.synthesize("q", [(1, "p")])

    def test_json_without_choices_raises_synthesis_error(self) -> None:
        synth = DeepSeekSynthesizer("dsk-key")
        with mock.patch(
            "httpx.post", return_value=self._response({"foo": "bar"})
        ):
            with self.assertRaises(SynthesisError):
                synth.synthesize("q", [(1, "p")])

    def test_empty_key_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            DeepSeekSynthesizer("   ")


class DefaultSynthesizerTests(unittest.TestCase):
    def _clear_keys(self):
        return mock.patch.dict(
            "os.environ",
            {
                "GEMINI_API_KEY": "",
                "GUIDE_GEMINI_API_KEY": "",
                "DEEPSEEK_API_KEY": "",
                "GUIDE_DEEPSEEK_API_KEY": "",
            },
            clear=False,
        )

    def test_no_keys_falls_back_to_extractive(self) -> None:
        with self._clear_keys():
            synth = default_synthesizer()
            self.assertIsInstance(synth, ExtractiveSynthesizer)

    def test_deepseek_alone_selects_deepseek(self) -> None:
        with self._clear_keys():
            with mock.patch.dict(
                "os.environ", {"DEEPSEEK_API_KEY": "dsk-key"}
            ):
                synth = default_synthesizer()
        self.assertIsInstance(synth, ChainSynthesizer)
        self.assertIsInstance(synth._synthesizers[0], DeepSeekSynthesizer)
        self.assertIsInstance(synth._synthesizers[1], ExtractiveSynthesizer)

    def test_deepseek_preferred_over_gemini(self) -> None:
        with self._clear_keys():
            with mock.patch.dict(
                "os.environ",
                {
                    "DEEPSEEK_API_KEY": "dsk-key",
                    "GEMINI_API_KEY": "gem-key",
                },
            ):
                synth = default_synthesizer()
        self.assertIsInstance(synth, ChainSynthesizer)
        self.assertIsInstance(synth._synthesizers[0], DeepSeekSynthesizer)
        self.assertIsInstance(synth._synthesizers[1], GeminiSynthesizer)
        self.assertIsInstance(synth._synthesizers[2], ExtractiveSynthesizer)


if __name__ == "__main__":
    unittest.main()
