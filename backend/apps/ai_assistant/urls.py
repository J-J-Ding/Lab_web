from django.urls import path
from . import views as v
urlpatterns=[path('ai/imports/',v.ImportsView.as_view()),path('ai/quota/',v.QuotaView.as_view()),path('ai/summaries/',v.SummaryView.as_view()),path('ai/imports/<uuid:pk>/',v.JobView.as_view()),path('ai/imports/<uuid:pk>/consent/',v.ConsentView.as_view()),path('ai/imports/<uuid:pk>/cancel/',v.CancelView.as_view()),path('ai/imports/<uuid:pk>/candidate/',v.CandidateView.as_view()),path('ai/imports/<uuid:pk>/apply/',v.ApplyView.as_view()),path('ai/imports/<uuid:pk>/matches/',v.MatchesView.as_view())]
