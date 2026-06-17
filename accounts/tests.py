from django.contrib.auth import get_user_model
from django.test import TestCase

H = {"HTTP_HOST": "localhost"}


class AccountMgmtTests(TestCase):
    def setUp(self):
        self.U = get_user_model()
        self.U.objects.create_user("a", "a@x.com", "pw-initial-1")
        self.client.login(username="a", password="pw-initial-1")

    def test_change_email(self):
        self.client.post("/accounts/settings/account/", {"action": "save_email", "email": "n@x.com"}, **H)
        self.assertEqual(self.U.objects.get(username="a").email, "n@x.com")

    def test_change_password(self):
        self.client.post("/accounts/settings/account/", {
            "action": "save_password", "old_password": "pw-initial-1",
            "new_password1": "Str0ngPass99", "new_password2": "Str0ngPass99"}, **H)
        self.client.logout()
        self.assertTrue(self.client.login(username="a", password="Str0ngPass99"))

    def test_delete_account(self):
        r = self.client.post("/accounts/settings/account/",
                             {"action": "delete_account", "confirm": "a"}, **H)
        self.assertEqual(r.status_code, 302)
        self.assertFalse(self.U.objects.filter(username="a").exists())

    def test_export(self):
        r = self.client.get("/accounts/export.json", **H)
        self.assertEqual(r.status_code, 200)
        self.assertIn("feeds", r.json())


class DataTransferTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("d", "", "pw")

    def test_import_pocket(self):
        from accounts.datatransfer import import_pocket
        from articles.models import Article

        html = '<ul><li><a href="https://ej.com/1" tags="x">Título 1</a></li>' \
               '<li><a href="https://ej.com/2">Título 2</a></li></ul>'
        res = import_pocket(self.user, html)
        self.assertEqual(res["saved"], 2)
        self.assertEqual(Article.objects.filter(feed__user=self.user, is_saved=True).count(), 2)

    def test_export_import_roundtrip(self):
        from accounts.datatransfer import export_user_data, import_user_data
        from feeds.models import Category, Feed, Source

        src = Source.objects.create(name="BBC", domain="bbc.com")
        cat = Category.objects.create(user=self.user, name="News")
        Feed.objects.create(user=self.user, source=src, url="http://bbc/rss", title="BBC", category=cat)
        data = export_user_data(self.user)

        other = get_user_model().objects.create_user("d2", "", "pw")
        import_user_data(other, data)
        self.assertTrue(Feed.objects.filter(user=other, url="http://bbc/rss").exists())
        self.assertTrue(Category.objects.filter(user=other, name="News").exists())


class PwaTests(TestCase):
    def test_service_worker_served_at_root(self):
        r = self.client.get("/sw.js", **H)
        self.assertEqual(r.status_code, 200)
        self.assertIn("javascript", r["Content-Type"])
        self.assertIn(b"notisnotis", r.content)
