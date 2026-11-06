from django.urls import path
from .views import UploadView,DownloadView
urlpatterns=[path('assets/',UploadView.as_view()),path('assets/<uuid:pk>/download/',DownloadView.as_view())]
