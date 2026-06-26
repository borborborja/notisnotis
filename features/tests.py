import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from features import has_feature
from features.models import UserEntitlements


class FeatureGatingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("u", "", "pw")

    def test_dormant_all_on(self):
        with patch.dict(os.environ, {"FEATURES_ENFORCED": "0"}):
            self.assertTrue(has_feature(self.user, "chat"))
            self.assertTrue(has_feature(self.user, "translate"))

    def test_global_disable(self):
        with patch.dict(os.environ, {"FEATURES_DISABLED": "chat"}):
            self.assertFalse(has_feature(self.user, "chat"))
            self.assertTrue(has_feature(self.user, "translate"))

    def test_enforced_tier_gating(self):
        UserEntitlements.objects.create(user=self.user, tier="free")
        with patch.dict(os.environ, {"FEATURES_ENFORCED": "1"}):
            self.user._ent_cache = "x"
            self.assertTrue(has_feature(self.user, "reader"))       # free
            self.assertFalse(has_feature(self.user, "translate"))   # pro
            self.assertFalse(has_feature(self.user, "chat"))        # max+beta

    def test_enforced_pro_tier(self):
        UserEntitlements.objects.create(user=self.user, tier="pro")
        with patch.dict(os.environ, {"FEATURES_ENFORCED": "1"}):
            self.user._ent_cache = "x"
            self.assertTrue(has_feature(self.user, "translate"))    # pro
            self.assertFalse(has_feature(self.user, "chat"))        # max

    def test_grant_overrides_tier(self):
        UserEntitlements.objects.create(user=self.user, tier="free", grants=["translate"])
        with patch.dict(os.environ, {"FEATURES_ENFORCED": "1"}):
            self.user._ent_cache = "x"
            self.assertTrue(has_feature(self.user, "translate"))

    def test_deny_overrides(self):
        UserEntitlements.objects.create(user=self.user, tier="max", beta_access=True, denies=["chat"])
        with patch.dict(os.environ, {"FEATURES_ENFORCED": "1"}):
            self.user._ent_cache = "x"
            self.assertFalse(has_feature(self.user, "chat"))

    def test_beta_requires_access(self):
        UserEntitlements.objects.create(user=self.user, tier="max", beta_access=False)
        with patch.dict(os.environ, {"FEATURES_ENFORCED": "1"}):
            self.user._ent_cache = "x"
            self.assertFalse(has_feature(self.user, "chat"))        # max pero beta sin acceso
            self.user._ent_cache = "x"
            self.assertTrue(has_feature(self.user, "mcp"))          # max no-beta

    def test_superuser_bypass(self):
        su = get_user_model().objects.create_superuser("admin", "", "pw")
        with patch.dict(os.environ, {"FEATURES_ENFORCED": "1"}):
            self.assertTrue(has_feature(su, "chat"))


class ModuleTests(TestCase):
    def setUp(self):
        from accounts.models import UserConfig
        self.U = get_user_model()
        self.user = self.U.objects.create_user("mu", "", "pw-mods-123")
        self.cfg = UserConfig.objects.create(user=self.user, data={})

    def test_default_all_on(self):
        from features.modules import enabled_modules, module_enabled
        self.assertEqual(enabled_modules(self.user), {"rss", "curation", "podcasts"})
        self.assertTrue(module_enabled(self.user, "rss"))

    def test_user_override_off(self):
        from features.modules import module_enabled
        self.cfg.data = {"module_curation": "0"}
        self.cfg.save()
        self.user.refresh_from_db()
        self.assertFalse(module_enabled(self.user, "curation"))
        self.assertTrue(module_enabled(self.user, "podcasts"))

    def test_env_locks_and_overrides_user(self):
        from features.modules import module_enabled, modules_state
        self.cfg.data = {"module_podcasts": "1"}  # el usuario lo quiere on…
        self.cfg.save()
        self.user.refresh_from_db()
        with patch.dict(os.environ, {"MODULE_PODCASTS": "0"}):  # …pero el operador manda
            self.assertFalse(module_enabled(self.user, "podcasts"))
            st = {m["module"]: m for m in modules_state(self.user)}
            self.assertTrue(st["podcasts"]["locked"])
            self.assertFalse(st["podcasts"]["enabled"])

    def test_module_required_redirects_when_off(self):
        from django.urls import reverse
        self.cfg.data = {"module_curation": "0"}
        self.cfg.save()
        self.client.force_login(self.user)
        r = self.client.get(reverse("stories:home"))
        self.assertEqual(r.status_code, 302)
        r2 = self.client.get(reverse("stories:home"), follow=True)
        self.assertContains(r2, "desactivada")

    def test_module_on_allows_view(self):
        from django.urls import reverse
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("stories:home")).status_code, 200)
