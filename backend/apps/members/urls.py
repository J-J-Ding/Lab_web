from django.urls import path
from .views import OwnDraftView,OwnOverviewView
urlpatterns=[path('members/me/draft/',OwnDraftView.as_view()),path('members/me/overview/',OwnOverviewView.as_view())]
