from django.urls import path
from .views import UploadView,DownloadView,DeleteView
urlpatterns=[path('assets/<uuid:pk>/delete/',DeleteView.as_view()),path('assets/',UploadView.as_view()),path('assets/<uuid:pk>/download/',DownloadView.as_view())]
