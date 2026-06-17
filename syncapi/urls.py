from django.urls import path

from . import fever, googlereader as gr

urlpatterns = [
    # Fever
    path("fever/", fever.endpoint, name="fever"),
    # Google Reader
    path("greader/accounts/ClientLogin", gr.client_login),
    path("greader/reader/api/0/token", gr.token),
    path("greader/reader/api/0/user-info", gr.user_info),
    path("greader/reader/api/0/subscription/list", gr.subscription_list),
    path("greader/reader/api/0/tag/list", gr.tag_list),
    path("greader/reader/api/0/unread-count", gr.unread_count),
    path("greader/reader/api/0/stream/items/ids", gr.stream_items_ids),
    path("greader/reader/api/0/stream/items/contents", gr.stream_items_contents),
    path("greader/reader/api/0/stream/contents/<path:stream>", gr.stream_contents),
    path("greader/reader/api/0/stream/contents", gr.stream_contents),
    path("greader/reader/api/0/edit-tag", gr.edit_tag),
    path("greader/reader/api/0/mark-all-as-read", gr.mark_all_as_read),
]
