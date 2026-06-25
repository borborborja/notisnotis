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
