from django.urls import path, re_path

from . import fever, googlereader as gr, gpodder

urlpatterns = [
    # gpodder (mygpo) — montado en /api/, así AntennaPod usa host = <raíz>.
    path("2/auth/<str:username>/login.json", gpodder.login, name="gp_login"),
    path("2/devices/<str:username>.json", gpodder.devices, name="gp_devices"),
    path("2/devices/<str:username>/<str:deviceid>.json", gpodder.device_update, name="gp_device"),
    path("2/subscriptions/<str:username>/<str:deviceid>.json", gpodder.subscriptions, name="gp_subs"),
    path("2/episodes/<str:username>.json", gpodder.episodes, name="gp_episodes"),
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
