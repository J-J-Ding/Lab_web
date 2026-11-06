from django.urls import path

from .views import HealthView,ReadinessView

urlpatterns = [
    path("ready/", ReadinessView.as_view()),path("health/", HealthView.as_view(), name="health")]
