"""Tests del servidor MCP.

El núcleo testeable en todo entorno es `_resolve_user()`: la frontera de
autenticación (token → usuario) de la que depende TODO el aislamiento por usuario.
La construcción del servidor (`build_server`) importa el SDK `mcp`, que exige
Python >= 3.10 (el dev local usa 3.9; CI/Docker usa 3.12), por eso ese bloque se
salta si la versión no llega.
"""
import os
import sys
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase

from accounts.models import ApiToken
from mcpserver.server import _resolve_user


class ResolveUserTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="x")
        self.bob = User.objects.create_user("bob", password="x")
        self.alice_token = ApiToken.objects.create(user=self.alice, name="t")

    def test_valid_token_resolves_owner(self):
        with mock.patch.dict(os.environ, {"NOTISNOTIS_API_TOKEN": self.alice_token.token}):
            self.assertEqual(_resolve_user(), self.alice)

    def test_token_belongs_only_to_its_owner(self):
        # El token de alice nunca resuelve a bob: base del aislamiento por usuario.
        with mock.patch.dict(os.environ, {"NOTISNOTIS_API_TOKEN": self.alice_token.token}):
            self.assertNotEqual(_resolve_user(), self.bob)

    def test_valid_token_updates_last_used(self):
        self.assertIsNone(self.alice_token.last_used)
        with mock.patch.dict(os.environ, {"NOTISNOTIS_API_TOKEN": self.alice_token.token}):
            _resolve_user()
        self.alice_token.refresh_from_db()
        self.assertIsNotNone(self.alice_token.last_used)

    def test_empty_token_raises(self):
        with mock.patch.dict(os.environ, {"NOTISNOTIS_API_TOKEN": ""}):
            with self.assertRaises(RuntimeError):
                _resolve_user()

    def test_invalid_token_raises(self):
        with mock.patch.dict(os.environ, {"NOTISNOTIS_API_TOKEN": "no-existe-este-token"}):
            with self.assertRaises(RuntimeError):
                _resolve_user()


@mock.patch.dict(os.environ, {}, clear=False)
class BuildServerTests(TestCase):
    """Smoke test del servidor completo. Requiere el SDK `mcp` (Python >= 3.10)."""

    def setUp(self):
        if sys.version_info < (3, 10):
            self.skipTest("El SDK mcp requiere Python >= 3.10 (dev local usa 3.9).")
        self.user = User.objects.create_user("carol", password="x")
        self.token = ApiToken.objects.create(user=self.user, name="t")

    def test_build_server_with_valid_token(self):
        os.environ["NOTISNOTIS_API_TOKEN"] = self.token.token
        from mcpserver.server import build_server

        server = build_server()  # no debe lanzar; registra las tools del usuario resuelto
        self.assertIsNotNone(server)
