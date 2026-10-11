import json
import os
import subprocess
import sys
import tempfile
import unittest
from importlib.resources import files
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from fastapi.testclient import TestClient

from founder_guide import (
    ChainTranscriptProvider,
    Cue,
    FixtureCatalogProvider,
    FixtureTranscriptProvider,
    Guide,
    NoCaptionError,
    Segment,
    Transcript,
    TranscriptApiProvider,
    normalize_cues,
    parse_vtt,
    segment_cues,
)
from founder_guide.http_api import create_app


FIXTURE = files("founder_guide").joinpath("demo_transcript.json")
CATALOG = files("founder_guide").joinpath("demo_catalog.json")
TRANSCRIPTS = files("founder_guide").joinpath("demo_transcripts.json")
SOURCE = str(Path(__file__).parents[1] / "src")


class AcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._prev_scopes = os.environ.get("GUIDE_SCOPES")
        os.environ["GUIDE_SCOPES"] = "shared,team,private"
        self.transcript = json.loads(FIXTURE.read_text())
        self.guide = Guide()

    def tearDown(self) -> None:
        if self._prev_scopes is None:
            os.environ.pop("GUIDE_SCOPES", None)
        else:
            os.environ["GUIDE_SCOPES"] = self._prev_scopes

    def test_spec_001_catalog_saves_at_most_20_unique_with_url_and_date(self) -> None:
        provider = FixtureCatalogProvider(Path(str(CATALOG)))
        sources = self.guide.catalog_channel(
            provider, "https://www.youtube.com/@demo", limit=20
        )

        self.assertEqual(len(sources), 20)
        self.assertEqual(len({source.video_id for source in sources}), 20)
        self.assertTrue(all(source.url and source.published_at for source in sources))
        self.assertEqual(self.guide.source_count, 20)
        self.assertEqual(self.guide.sources, sources)
        self.assertNotIn("demo-v21", {source.video_id for source in sources})
        self.assertNotIn("demo-v22", {source.video_id for source in sources})

    def test_spec_002_automatic_fallback_records_provenance(self) -> None:
        provider = FixtureTranscriptProvider(Path(str(TRANSCRIPTS)))
        result = self.guide.ingest_video(provider, "demo-auto-only", ["es"])

        self.assertEqual(result.transcript_kind, "automatic")
        self.assertTrue(result.created)
        self.assertGreaterEqual(len(result.segments), 1)

        preferred = self.guide.ingest_video(provider, "demo-founder-001", ["es"])
        self.assertEqual(preferred.transcript_kind, "manual")

        with self.assertRaises(NoCaptionError) as ctx:
            self.guide.ingest_video(provider, "demo-no-caption", ["es"])
        self.assertEqual(ctx.exception.error_code, "no_caption")

    def test_spec_003_reingestion_is_idempotent(self) -> None:
        first = self.guide.ingest(self.transcript)
        second = self.guide.ingest(self.transcript)

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.segments, second.segments)
        self.assertEqual(self.guide.document_count, 1)
        self.assertEqual(self.guide.segment_count, 2)

    def test_spec_004_citations_are_only_search_hits_with_timestamps(self) -> None:
        result = self.guide.ingest(self.transcript)
        hits = self.guide.search("validar usuarios")
        answer = self.guide.answer("validar usuarios")

        self.assertGreaterEqual(len(hits), 2)
        self.assertEqual(
            {citation.citation_id for citation in answer.citations},
            {hit.citation_id for hit in hits},
        )
        self.assertTrue(
            all(
                citation.url.endswith(f"&t={citation.start_seconds}s")
                for citation in answer.citations
            )
        )
        self.assertTrue(
            all(60 <= segment.end_seconds - segment.start_seconds <= 120
                for segment in result.segments)
        )

    def test_ingest_pending_reports_captions_and_skips_missing(self) -> None:
        catalog_payload = {
            "channel": "https://www.youtube.com/@demo",
            "videos": [
                {
                    "video_id": "demo-auto-only",
                    "url": "https://youtube.com/watch?v=demo-auto-only",
                    "published_at": "2024-02-01T00:00:00Z",
                },
                {
                    "video_id": "demo-no-caption",
                    "url": "https://youtube.com/watch?v=demo-no-caption",
                    "published_at": "2024-02-02T00:00:00Z",
                },
                {
                    "video_id": "demo-founder-001",
                    "url": "https://youtube.com/watch?v=demo-founder-001",
                    "published_at": "2024-02-03T00:00:00Z",
                },
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            catalog_path = Path(directory) / "catalog.json"
            catalog_path.write_text(json.dumps(catalog_payload))
            self.guide.catalog_channel(
                FixtureCatalogProvider(catalog_path),
                "https://www.youtube.com/@demo",
                limit=20,
            )
        report = self.guide.ingest_pending(
            FixtureTranscriptProvider(Path(str(TRANSCRIPTS))),
            ["es"],
            limit=20,
        )
        by_id = {item["video_id"]: item for item in report}
        self.assertEqual(by_id["demo-auto-only"]["status"], "ingested")
        self.assertEqual(by_id["demo-auto-only"]["transcript_kind"], "automatic")
        self.assertEqual(by_id["demo-no-caption"]["status"], "no_caption")
        self.assertEqual(by_id["demo-founder-001"]["status"], "ingested")
        self.assertEqual(by_id["demo-founder-001"]["transcript_kind"], "manual")
        self.assertEqual(self.guide.document_count, 2)

    def test_transcript_api_provider_maps_cues_and_asr_kind(self) -> None:
        class _Response:
            status_code = 200

            def json(self) -> dict:
                return {
                    "video_id": "abc123xyz00",
                    "language": "asr-en",
                    "transcript": [
                        {"text": "Talk to users first.", "start": 0.0, "duration": 30.0},
                        {"text": "Validate before building.", "start": 30.0, "duration": 30.0},
                    ],
                }

        class _Client:
            def get(self, url: str, **kwargs: object) -> _Response:
                self.url = url
                self.kwargs = kwargs
                return _Response()

        client = _Client()
        provider = TranscriptApiProvider("test-key", client=client)
        result = provider.fetch("abc123xyz00", ["es", "en"])
        self.assertEqual(result.video_id, "abc123xyz00")
        self.assertEqual(result.language, "en")
        self.assertEqual(result.kind, "automatic")
        self.assertEqual(len(result.cues), 2)
        self.assertIn("language", client.kwargs["params"])
        self.assertEqual(
            client.kwargs["headers"]["Authorization"], "Bearer test-key"
        )

    def test_transcript_api_provider_404_is_no_caption(self) -> None:
        class _Response:
            status_code = 404

            def json(self) -> dict:
                return {"detail": "missing"}

        class _Client:
            def get(self, url: str, **kwargs: object) -> _Response:
                return _Response()

        provider = TranscriptApiProvider("test-key", client=_Client())
        with self.assertRaises(NoCaptionError):
            provider.fetch("missingvid1", ["en"])

    def test_transcript_api_provider_401_is_runtime_error(self) -> None:
        class _Response:
            status_code = 401

            def json(self) -> dict:
                return {"detail": "bad key"}

        class _Client:
            def get(self, url: str, **kwargs: object) -> _Response:
                return _Response()

        provider = TranscriptApiProvider("bad", client=_Client())
        with self.assertRaises(RuntimeError):
            provider.fetch("abc123xyz00", ["en"])

    def test_ingest_pending_skips_too_short_transcript(self) -> None:
        catalog_payload = {
            "channel": "https://www.youtube.com/@demo",
            "videos": [
                {
                    "video_id": "demo-too-short",
                    "url": "https://youtube.com/watch?v=demo-too-short",
                    "published_at": "2024-02-04T00:00:00Z",
                },
                {
                    "video_id": "demo-auto-only",
                    "url": "https://youtube.com/watch?v=demo-auto-only",
                    "published_at": "2024-02-01T00:00:00Z",
                },
            ],
        }
        transcripts_payload = {
            "videos": {
                "demo-too-short": {
                    "url": "https://youtube.com/watch?v=demo-too-short",
                    "manual": {
                        "es": [
                            {"start": 0, "duration": 10, "text": "Clip corto."},
                        ]
                    },
                    "automatic": {},
                },
                "demo-auto-only": json.loads(Path(str(TRANSCRIPTS)).read_text())[
                    "videos"
                ]["demo-auto-only"],
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            catalog_path = Path(directory) / "catalog.json"
            transcripts_path = Path(directory) / "transcripts.json"
            catalog_path.write_text(json.dumps(catalog_payload))
            transcripts_path.write_text(json.dumps(transcripts_payload))
            self.guide.catalog_channel(
                FixtureCatalogProvider(catalog_path),
                "https://www.youtube.com/@demo",
                limit=20,
            )
            report = self.guide.ingest_pending(
                FixtureTranscriptProvider(transcripts_path),
                ["es"],
                limit=20,
            )
        by_id = {item["video_id"]: item for item in report}
        self.assertEqual(by_id["demo-too-short"]["status"], "invalid_transcript")
        self.assertEqual(by_id["demo-auto-only"]["status"], "ingested")
        self.assertEqual(self.guide.document_count, 1)

    def test_spec_005_notes_are_isolated_by_scope(self) -> None:
        self.guide.ingest(self.transcript)
        note = self.guide.add_note(
            self.transcript["video_id"],
            "team",
            "Nota secreta team sobre runway interno",
            stage="fundraising",
        )

        hidden = self.guide.search("runway interno", scope="private")
        visible = self.guide.search("runway interno", scope="team")

        self.assertNotIn(note.note_id, {hit.citation_id for hit in hidden})
        self.assertIn(note.note_id, {hit.citation_id for hit in visible})
        self.assertEqual(visible[0].text, note.content)

    def test_http_search_and_answer_endpoints(self) -> None:
        self.guide.ingest(self.transcript)
        client = TestClient(create_app(self.guide))

        search = client.get(
            "/v1/search",
            params={"q": "validar usuarios", "scope": "shared", "limit": 10},
        )
        self.assertEqual(search.status_code, 200)
        search_payload = search.json()
        self.assertGreaterEqual(len(search_payload["items"]), 2)
        first_source = search_payload["items"][0]["source"]
        self.assertEqual(first_source["title"], "Cómo validar con usuarios (demo)")
        self.assertIn("startSeconds", first_source)

        answer = client.post(
            "/v1/answers",
            json={"question": "validar usuarios", "scope": "shared"},
        )
        self.assertEqual(answer.status_code, 200)
        answer_payload = answer.json()
        self.assertFalse(answer_payload["insufficientEvidence"])
        self.assertTrue(answer_payload["answer"])
        self.assertGreaterEqual(len(answer_payload["citations"]), 2)
        for citation in answer_payload["citations"]:
            self.assertEqual(citation["title"], "Cómo validar con usuarios (demo)")
            self.assertIsInstance(citation["startSeconds"], int)
            self.assertTrue(
                citation["url"].endswith(f"&t={citation['startSeconds']}s")
            )

        bad = client.get("/v1/search", params={"q": "x", "scope": "nope"})
        self.assertEqual(bad.status_code, 400)

    def test_http_bearer_auth_and_admin_ingest(self) -> None:
        provider = FixtureTranscriptProvider(Path(str(TRANSCRIPTS)))
        app = create_app(
            self.guide, token="secret", transcript_provider=provider
        )
        client = TestClient(app)

        denied = client.get("/v1/search", params={"q": "x"})
        self.assertEqual(denied.status_code, 401)

        headers = {"Authorization": "Bearer secret"}
        ok = client.get(
            "/healthz",
        )
        self.assertEqual(ok.status_code, 200)

        search = client.get(
            "/v1/search",
            params={"q": "validar", "scope": "shared"},
            headers=headers,
        )
        self.assertEqual(search.status_code, 200)

        missing = client.post(
            "/v1/admin/ingestions",
            json={"videoId": "demo-no-caption", "languages": ["es"]},
            headers=headers,
        )
        self.assertEqual(missing.status_code, 422)
        self.assertEqual(missing.json()["detail"]["error"]["code"], "NO_CAPTION")

        created = client.post(
            "/v1/admin/ingestions",
            json={"videoId": "demo-auto-only", "languages": ["es"]},
            headers={**headers, "Idempotency-Key": "demo-auto-only-es"},
        )
        self.assertEqual(created.status_code, 200)
        self.assertEqual(created.json()["transcriptKind"], "automatic")
        self.assertTrue(created.json()["created"])

        verify = client.get("/v1/admin/verify", headers=headers)
        self.assertEqual(verify.status_code, 200)
        self.assertTrue(verify.json()["ok"])

    def test_verify_corpus_reports_healthy_demo(self) -> None:
        self.guide.ingest(self.transcript)
        report = self.guide.verify_corpus()
        self.assertTrue(report["ok"])
        self.assertEqual(report["documents"], 1)
        self.assertGreaterEqual(report["segments"], 1)
        self.assertEqual(report["issues"], [])

    def test_verify_corpus_allows_tail_merged_last_segment(self) -> None:
        # A sub-60s tail merges into the previous batch (segment_cues tail
        # merge), so the final segment legitimately exceeds 120s.
        cues = [
            {"start": i, "duration": 1.0, "text": f"palabra {i}"}
            for i in range(161)
        ]
        self.guide.ingest(
            {
                "video_id": "demo-tail-merge",
                "language": "es",
                "url": "https://youtube.com/watch?v=demo-tail-merge",
                "kind": "automatic",
                "cues": cues,
            }
        )
        report = self.guide.verify_corpus()
        self.assertTrue(report["ok"])
        self.assertEqual(report["issues"], [])

    def test_verify_corpus_flags_non_last_segment_out_of_range(self) -> None:
        guide = Guide()
        url = "https://youtube.com/watch?v=v-corrupt"
        guide._documents[("v-corrupt", "es", "hash")] = (
            Segment("seg_a", "v-corrupt", "es", url, 0, 140, "primero"),
            Segment("seg_b", "v-corrupt", "es", url, 150, 210, "segundo"),
        )
        guide._active[("v-corrupt", "es")] = "hash"
        report = guide.verify_corpus()
        codes = [issue["code"] for issue in report["issues"]]
        self.assertEqual(
            [code for code in codes if code == "segment_out_of_range"],
            ["segment_out_of_range"],
        )

    def test_sqlite_persists_ingest_and_notes_across_instances(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "guide.sqlite"
            first = Guide(db_path=db_path)
            first.ingest(self.transcript)
            note = first.add_note(
                self.transcript["video_id"],
                "shared",
                "Nota persistida de validacion",
                stage="validation",
            )
            self.assertEqual(first.document_count, 1)

            second = Guide(db_path=db_path)
            self.assertEqual(second.document_count, 1)
            self.assertEqual(second.segment_count, first.segment_count)
            hits = second.search("validacion", scope="shared", stage="validation")
            self.assertIn(note.note_id, {hit.citation_id for hit in hits})
            answer = second.answer("validar usuarios")
            self.assertFalse(answer.insufficient_evidence)

    def test_notes_can_filter_by_stage(self) -> None:
        self.guide.ingest(self.transcript)
        video_id = self.transcript["video_id"]
        fund = self.guide.add_note(
            video_id, "shared", "Consejo de runway para fundraising", stage="fundraising"
        )
        self.guide.add_note(
            video_id, "shared", "Consejo de runway para mvp", stage="mvp"
        )

        hits = self.guide.search("runway", scope="shared", stage="fundraising")
        note_ids = {hit.citation_id for hit in hits}
        self.assertIn(fund.note_id, note_ids)
        self.assertTrue(all("mvp" not in hit.text for hit in hits if hit.citation_id.startswith("note_")))

    def test_spec_006_marks_insufficient_evidence(self) -> None:
        self.guide.ingest(self.transcript)
        answer = self.guide.answer("impuestos aduanales")

        self.assertTrue(answer.insufficient_evidence)
        self.assertEqual(answer.text, "")
        self.assertEqual(answer.citations, ())

    def test_answer_is_extractively_built_from_recovered_hits(self) -> None:
        self.guide.ingest(self.transcript)
        answer = self.guide.answer("validar usuarios")
        self.assertFalse(answer.insufficient_evidence)
        self.assertEqual(answer.text, " ".join(hit.text for hit in self.guide.search("validar usuarios")))

    def test_segment_rejects_a_cue_longer_than_120_seconds(self) -> None:
        with self.assertRaises(ValueError):
            segment_cues([Cue(0, 121, "x.")])

    def test_demo_uses_packaged_fixture_from_any_working_directory(self) -> None:
        environment = os.environ | {"PYTHONPATH": SOURCE}
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, "-m", "founder_guide", "demo"],
                cwd=directory,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            )
        payload = json.loads(result.stdout)
        self.assertTrue(payload["answer"])
        self.assertFalse(payload["insufficient_evidence"])

    def test_catalog_channel_cli_uses_packaged_fixture(self) -> None:
        environment = os.environ | {"PYTHONPATH": SOURCE}
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "founder_guide",
                    "catalog-channel",
                    "https://www.youtube.com/@demo",
                    "--limit",
                    "20",
                ],
                cwd=directory,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["count"], 20)
        self.assertEqual(len(payload["sources"]), 20)
        self.assertTrue(
            all(item["url"] and item["published_at"] for item in payload["sources"])
        )

    def test_add_note_cli_prints_note(self) -> None:
        environment = os.environ | {"PYTHONPATH": SOURCE}
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "founder_guide",
                    "add-note",
                    "demo-founder-001",
                    "--scope",
                    "team",
                    "--stage",
                    "fundraising",
                    "--content",
                    "Nota de prueba cli",
                    "--url",
                    "https://youtube.com/watch?v=demo-founder-001",
                ],
                cwd=directory,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["scope"], "team")
        self.assertEqual(payload["stage"], "fundraising")
        self.assertEqual(payload["content"], "Nota de prueba cli")
        self.assertTrue(payload["note_id"].startswith("note_"))

    def test_ingest_video_cli_uses_automatic_fallback(self) -> None:
        environment = os.environ | {"PYTHONPATH": SOURCE}
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "founder_guide",
                    "ingest-video",
                    "demo-auto-only",
                    "--languages",
                    "es",
                ],
                cwd=directory,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["transcript_kind"], "automatic")
        self.assertTrue(payload["created"])
        self.assertGreaterEqual(payload["segment_count"], 1)

    def test_normalization_removes_markup_spaces_and_repetitions(self) -> None:
        cues = normalize_cues(
            [
                {"start": 0, "duration": 30, "text": "<b>Uno   dos</b>"},
                {"start": 30, "duration": 30, "text": "<b>Uno   dos</b>"},
                {"start": 60, "duration": 30, "text": "Uno dos tres."},
            ]
        )

        self.assertEqual([cue.text for cue in cues], ["Uno dos", "tres."])
        self.assertEqual(len(segment_cues(cues)), 1)

    def test_parse_vtt_extracts_cues(self) -> None:
        vtt = """WEBVTT

00:00:01.000 --> 00:00:03.500
Hola <c>mundo</c>

00:00:03.500 --> 00:00:05.000
Segundo cue.
"""
        cues = parse_vtt(vtt)
        self.assertEqual(len(cues), 2)
        self.assertEqual(cues[0]["start"], 1.0)
        self.assertAlmostEqual(cues[0]["duration"], 2.5)
        self.assertEqual(cues[0]["text"], "Hola mundo")
        self.assertEqual(cues[1]["text"], "Segundo cue.")

    def test_chain_transcript_falls_back_to_second_provider(self) -> None:
        class Boom:
            def fetch(self, video_id: str, languages: list[str]) -> Transcript:
                raise NoCaptionError(video_id)

        class Ok:
            def fetch(self, video_id: str, languages: list[str]) -> Transcript:
                return Transcript(
                    video_id,
                    languages[0],
                    f"https://youtube.com/watch?v={video_id}",
                    "automatic",
                    ({"start": 0, "duration": 30, "text": "ok"},),
                )

        provider = ChainTranscriptProvider([Boom(), Ok()])
        result = provider.fetch("vid-1", ["es"])
        self.assertEqual(result.kind, "automatic")
        self.assertEqual(result.cues[0]["text"], "ok")

    def test_catalog_title_flows_into_citations_after_reload(self) -> None:
        catalog_payload = {
            "channel": "https://www.youtube.com/@demo",
            "videos": [
                {
                    "video_id": "demo-founder-001",
                    "url": "https://youtube.com/watch?v=demo-founder-001",
                    "published_at": "2024-02-03T00:00:00Z",
                    "title": "Validar con usuarios",
                },
            ],
        }
        transcript = {
            key: value for key, value in self.transcript.items() if key != "title"
        }
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "guide.sqlite"
            catalog_path = Path(directory) / "catalog.json"
            catalog_path.write_text(json.dumps(catalog_payload))
            first = Guide(db_path=db_path)
            first.catalog_channel(
                FixtureCatalogProvider(catalog_path),
                "https://www.youtube.com/@demo",
            )
            first.ingest(transcript)

            second = Guide(db_path=db_path)
            hits = second.search("validar usuarios")
            answer = second.answer("validar usuarios")

        self.assertTrue(hits)
        self.assertTrue(all(hit.title == "Validar con usuarios" for hit in hits))
        self.assertTrue(
            all(citation.title == "Validar con usuarios"
                for citation in answer.citations)
        )

    def test_http_ui_is_served(self) -> None:
        guide = Guide()
        guide.ingest(self.transcript)
        client = TestClient(create_app(guide, token=""))
        response = client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers.get("content-type", ""))
        self.assertIn("/v1/answers", response.text)
        self.assertIn(
            '<option value="shared">shared</option>', response.text
        )
        self.assertIn('id="stage"', response.text)
        self.assertIn("rel=\"icon\"", response.text)

    def test_http_ui_scopes_are_configurable(self) -> None:
        client = TestClient(create_app(Guide(), token="", scopes=("shared", "lab")))
        response = client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn('<option value="lab">lab</option>', response.text)
        self.assertNotIn(
            '<option value="team">team</option>', response.text
        )


if __name__ == "__main__":
    unittest.main()
