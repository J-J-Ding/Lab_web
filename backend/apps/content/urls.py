from django.urls import path
from .views import ParticipationsView
urlpatterns=[path('content/participations/',ParticipationsView.as_view())]
