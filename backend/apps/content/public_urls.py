from django.urls import path
from . import public_views as v
from apps.assets.public_views import PublicAsset
urlpatterns=[path('public/legacy/',v.LegacyResolve.as_view()),path('public/assets/<uuid:pk>/',PublicAsset.as_view()),
    path('public/content/',v.ContentList.as_view()),path('public/content/<uuid:pk>/',v.ContentDetail.as_view()),
    path('public/members/',v.MemberList.as_view()),path('public/members/<str:slug>/',v.MemberDetail.as_view()),
    path('public/members/<str:slug>/achievements/',v.Achievements.as_view()),
    path('public/projects/<uuid:pk>/outputs/',v.Outputs.as_view()),path('public/graduates/',v.Graduates.as_view()),
    path('public/pages/<str:key>/',v.FixedPage.as_view()),
]
