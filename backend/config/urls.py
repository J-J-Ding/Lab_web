from django.urls import include, path

urlpatterns = [
    path("api/", include("apps.content.direct_urls")),
    path("api/", include("apps.analytics.urls")),
    path("api/", include("apps.ai_assistant.urls")),
    path("api/", include("apps.content.public_urls")),
    path("api/", include("apps.core.urls")),
    path("api/", include("apps.accounts.urls")),
    path("api/", include("apps.members.urls")),
    path("api/", include("apps.content.urls")),
    path("api/", include("apps.workflow.urls")),
    path("api/", include("apps.assets.urls")),
]
