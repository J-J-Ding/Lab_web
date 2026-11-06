from django.urls import path
from . import views as v
urlpatterns=[path('public/stats/overview/',v.PublicOverview.as_view()),path('public/stats/annual/',v.PublicAnnual.as_view()),path('stats/me/',v.Me.as_view()),path('admin/stats/overview/',v.AdminOverview.as_view()),path('admin/stats/review/',v.AdminReview.as_view()),path('admin/stats/export/',v.Export.as_view())]
