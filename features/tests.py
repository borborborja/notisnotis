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
