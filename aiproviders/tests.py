"""Tests de la abstracción de IA (provider mock, sin red ni claves).

Cubren: factoría de clientes, cascada de configuración (.env > usuario > default),
el provider mock determinista y el parseo tolerante de JSON.
"""
import os
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase

from accounts.models import UserConfig
from aiproviders.base import AIError, BaseChatProvider
from aiproviders.client import get_chat_client, get_embed_client
from aiproviders.config import effective_config
from aiproviders.providers.mock import MockChatProvider, MockEmbedProvider


class ClientFactoryTests(TestCase):
    def test_default_clients_are_mock(self):
        # Sin .env ni config de usuario, la cascada cae al default "mock".
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AI_DEFAULT_PROVIDER", None)
            os.environ.pop("AI_EMBED_PROVIDER", None)
            self.assertIsInstance(get_chat_client(), MockChatProvider)
            self.assertIsInstance(get_embed_client(), MockEmbedProvider)

    def test_unknown_provider_raises(self):
        user = User.objects.create_user("u1", password="x")
        UserConfig.objects.create(user=user, data={"chat_provider": "nope"})
        with self.assertRaises(ValueError):
            get_chat_client(user)


class CascadeTests(TestCase):
    def test_default_value(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AI_DEFAULT_PROVIDER", None)
            cfg = effective_config()
            self.assertEqual(cfg["chat_provider"], "mock")
            self.assertEqual(cfg["embed_dim"], 256)

    def test_user_override(self):
        user = User.objects.create_user("u2", password="x")
        UserConfig.objects.create(user=user, data={"chat_provider": "ollama"})
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AI_DEFAULT_PROVIDER", None)
            cfg = effective_config(user)
            # El usuario manda sobre el default cuando el operador no lo ha fijado.
            self.assertEqual(cfg["chat_provider"], "ollama")

    def test_operator_env_lock_wins_over_user(self):
        user = User.objects.create_user("u3", password="x")
        UserConfig.objects.create(user=user, data={"chat_provider": "ollama"})
        with mock.patch.dict(os.environ, {"AI_DEFAULT_PROVIDER": "openrouter"}):
            cfg = effective_config(user)
            # .env del operador bloquea el campo: gana sobre la preferencia del usuario.
            self.assertEqual(cfg["chat_provider"], "openrouter")


class MockProviderTests(TestCase):
    def test_chat_text_is_deterministic(self):
        c = MockChatProvider()
        msgs = [{"role": "user", "content": "hola mundo"}]
        self.assertEqual(c.chat(msgs), c.chat(msgs))
        self.assertIn("[mock]", c.chat(msgs))

    def test_chat_json_shapes_per_task(self):
        c = MockChatProvider()
        bias = c.chat([{"role": "user", "content": "estima el sesgo"}], json=True)
        self.assertIn("bias", bias)
        persp = c.chat([{"role": "user", "content": "redacta perspectivas y headline"}], json=True)
        self.assertIn("perspectives", persp)
        enrich = c.chat([{"role": "user", "content": "enriquece este articulo"}], json=True)
        self.assertIn("claims", enrich)

    def test_list_models(self):
        self.assertEqual(MockChatProvider().list_models(), ["mock-small", "mock-large"])
        self.assertEqual(MockEmbedProvider().list_models(), ["mock-embed"])

    def test_embed_dim_and_normalized(self):
        e = MockEmbedProvider(dim=16)
        vecs = e.embed(["uno dos tres", "uno dos tres"])
        self.assertEqual(len(vecs), 2)
        self.assertEqual(len(vecs[0]), 16)
        # Vector normalizado (norma ~1) y determinista para el mismo texto.
        norm = sum(v * v for v in vecs[0]) ** 0.5
        self.assertAlmostEqual(norm, 1.0, places=5)
        self.assertEqual(vecs[0], vecs[1])


class ParseJsonTests(TestCase):
    def test_plain_json(self):
        self.assertEqual(BaseChatProvider.parse_json('{"a": 1}'), {"a": 1})

    def test_fenced_json(self):
        self.assertEqual(BaseChatProvider.parse_json('```json\n{"a": 1}\n```'), {"a": 1})

    def test_embedded_json(self):
        self.assertEqual(BaseChatProvider.parse_json('Claro: {"a": 1} listo'), {"a": 1})

    def test_invalid_raises(self):
        with self.assertRaises(AIError):
            BaseChatProvider.parse_json("esto no es json")


class _FakeResp:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self):
        return self._payload


class OpenAIProviderTests(TestCase):
    def test_embed_batch_and_dimensions(self):
        from aiproviders.providers.openai import OpenAIEmbedProvider

        payload = {"data": [
            {"index": 1, "embedding": [0.1, 0.2]},
            {"index": 0, "embedding": [0.3, 0.4]},  # desordenado a propósito
        ]}
        with mock.patch("aiproviders.providers.openai.requests.post",
                        return_value=_FakeResp(payload)) as post:
            e = OpenAIEmbedProvider(model="text-embedding-3-small", dim=2, api_key="k", timeout=5)
            vecs = e.embed(["uno", "dos"])
        # Se reordena por index y se devuelven los vectores en orden de entrada.
        self.assertEqual(vecs, [[0.3, 0.4], [0.1, 0.2]])
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["input"], ["uno", "dos"])  # batch
        self.assertEqual(body["dimensions"], 2)          # recorte a embed_dim
        headers = post.call_args.kwargs["headers"]
        self.assertEqual(headers["Authorization"], "Bearer k")
        self.assertTrue(post.call_args.args[0].endswith("/embeddings"))

    def test_embed_without_key_raises(self):
        from aiproviders.providers.openai import OpenAIEmbedProvider

        with self.assertRaises(AIError):
            OpenAIEmbedProvider(dim=2, api_key="", timeout=5).embed(["x"])

    def test_embed_http_error_raises(self):
        from aiproviders.providers.openai import OpenAIEmbedProvider

        with mock.patch("aiproviders.providers.openai.requests.post",
                        return_value=_FakeResp({"error": "bad"}, status_code=401)):
            with self.assertRaises(AIError):
                OpenAIEmbedProvider(dim=2, api_key="k", timeout=5).embed(["x"])

    def test_chat_json_mode(self):
        from aiproviders.providers.openai import OpenAIChatProvider

        payload = {"choices": [{"message": {"content": '{"ok": true}'}}]}
        with mock.patch("aiproviders.providers.openai.requests.post",
                        return_value=_FakeResp(payload)) as post:
            c = OpenAIChatProvider(model="gpt-4o-mini", api_key="k", timeout=5)
            out = c.chat([{"role": "user", "content": "hola"}], json=True)
        self.assertEqual(out, {"ok": True})
        self.assertEqual(post.call_args.kwargs["json"]["response_format"], {"type": "json_object"})
        self.assertTrue(post.call_args.args[0].endswith("/chat/completions"))


class JinaProviderTests(TestCase):
    def test_embed_batch_and_dimensions(self):
        from aiproviders.providers.jina import JinaEmbedProvider

        payload = {"data": [
            {"index": 0, "embedding": [1.0, 0.0]},
            {"index": 1, "embedding": [0.0, 1.0]},
        ]}
        with mock.patch("aiproviders.providers.jina.requests.post",
                        return_value=_FakeResp(payload)) as post:
            e = JinaEmbedProvider(model="jina-embeddings-v3", dim=2, api_key="k", timeout=5)
            vecs = e.embed(["a", "b"])
        self.assertEqual(vecs, [[1.0, 0.0], [0.0, 1.0]])
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["input"], ["a", "b"])
        self.assertEqual(body["dimensions"], 2)

    def test_embed_without_key_raises(self):
        from aiproviders.providers.jina import JinaEmbedProvider

        with self.assertRaises(AIError):
            JinaEmbedProvider(dim=2, api_key="", timeout=5).embed(["x"])


class ProviderSelectionTests(TestCase):
    """La cascada selecciona los nuevos providers y la UI los expone como campos editables."""

    def test_get_clients_for_openai_and_jina(self):
        from aiproviders.providers.jina import JinaEmbedProvider
        from aiproviders.providers.openai import OpenAIChatProvider, OpenAIEmbedProvider

        user = User.objects.create_user("sel", password="x")
        UserConfig.objects.create(user=user, data={
            "chat_provider": "openai", "embed_provider": "jina",
        })
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AI_DEFAULT_PROVIDER", None)
            os.environ.pop("AI_EMBED_PROVIDER", None)
            self.assertIsInstance(get_chat_client(user), OpenAIChatProvider)
            self.assertIsInstance(get_embed_client(user), JinaEmbedProvider)
        user2 = User.objects.create_user("sel2", password="x")
        UserConfig.objects.create(user=user2, data={"embed_provider": "openai"})
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AI_EMBED_PROVIDER", None)
            self.assertIsInstance(get_embed_client(user2), OpenAIEmbedProvider)

    def test_new_fields_are_editable_in_ui(self):
        from aiproviders.config import editable_fields

        user = User.objects.create_user("ui", password="x")
        with mock.patch.dict(os.environ, {}, clear=False):
            for var in ("OPENAI_API_KEY", "JINA_API_KEY"):
                os.environ.pop(var, None)
            keys = {f["key"] for f in editable_fields(user)}
        self.assertIn("openai_api_key", keys)
        self.assertIn("jina_api_key", keys)

    def test_operator_env_locks_openai_key(self):
        from aiproviders.config import editable_fields, locked_fields

        user = User.objects.create_user("lock", password="x")
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-operador"}):
            editable_keys = {f["key"] for f in editable_fields(user)}
            locked_keys = {f["key"] for f in locked_fields()}
        # Fijada por el operador: sale de editables y aparece como bloqueada (solo lectura).
        self.assertNotIn("openai_api_key", editable_keys)
        self.assertIn("openai_api_key", locked_keys)


class WhisperLocalTests(TestCase):
    def test_transcribe_posts_openai_format(self):
        from unittest import mock
        from aiproviders.providers.whisper_local import WhisperLocalTranscribeProvider

        class _R:
            status_code = 200
            def json(self): return {"text": "hola mundo"}
        captured = {}
        def _post(url, **kw):
            captured["url"] = url; captured["data"] = kw.get("data"); return _R()
        with mock.patch("aiproviders.providers.whisper_local.requests.post", _post):
            p = WhisperLocalTranscribeProvider(model="Systran/faster-whisper-small", url="http://w:8000")
            out = p.transcribe(b"audio", lang="es")
        self.assertEqual(out, "hola mundo")
        self.assertTrue(captured["url"].endswith("/v1/audio/transcriptions"))
        self.assertEqual(captured["data"]["model"], "Systran/faster-whisper-small")
        self.assertEqual(captured["data"]["language"], "es")

    def test_list_models_merges_installed_and_common(self):
        from unittest import mock
        from aiproviders.providers.whisper_local import WhisperLocalTranscribeProvider

        class _R:
            status_code = 200
            def json(self): return {"data": [{"id": "Systran/faster-whisper-base"}]}
        with mock.patch("aiproviders.providers.whisper_local.requests.get", return_value=_R()):
            models = WhisperLocalTranscribeProvider(url="http://w:8000").list_models()
        self.assertIn("Systran/faster-whisper-base", models)
        self.assertIn("Systran/faster-whisper-large-v3", models)  # de la lista curada

    def test_download_model_calls_endpoint(self):
        from unittest import mock
        from aiproviders.providers.whisper_local import WhisperLocalTranscribeProvider

        class _R:
            status_code = 200
            text = ""
        with mock.patch("aiproviders.providers.whisper_local.requests.post", return_value=_R()) as p:
            WhisperLocalTranscribeProvider(url="http://w:8000").download_model("Systran/faster-whisper-small")
        self.assertIn("/v1/models/Systran/faster-whisper-small", p.call_args[0][0])


class TranscribeModelsViewTests(TestCase):
    def setUp(self):
        from accounts.models import UserConfig
        self.u = User.objects.create_user("tm", "", "pw-tm-12345")
        UserConfig.objects.create(user=self.u, data={"transcribe_provider": "mock"})
        self.client.login(username="tm", password="pw-tm-12345")

    def test_ai_models_transcribe(self):
        r = self.client.post("/accounts/settings/ai/models/",
                             {"kind": "transcribe", "transcribe_provider": "mock"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "mock-whisper")

    def test_download_endpoint(self):
        r = self.client.post("/accounts/settings/transcribe/download/",
                             {"transcribe_provider": "mock", "transcribe_model": "x"})
        self.assertEqual(r.status_code, 200)
