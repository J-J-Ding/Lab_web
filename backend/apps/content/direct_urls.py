from django.urls import path,re_path
from . import direct_views as v
from apps.members import submissions as submissions
from apps.members import cv
from apps.members.options import Options
from .carousel import Carousel
from . import batch_views as batch
urlpatterns=[
 path('content/imports/template/',batch.Template.as_view()),path('content/imports/',batch.Batches.as_view()),
 path('content/imports/<uuid:pk>/',batch.Item.as_view()),path('content/imports/<uuid:pk>/consent/',batch.Consent.as_view()),
 path('content/imports/<uuid:pk>/confirm/',batch.Confirm.as_view()),path('content/imports/<uuid:pk>/cancel/',batch.Cancel.as_view()),
 path('admin/carousel/',Carousel.as_view()),path('admin/carousel/<uuid:pk>/',Carousel.as_view()),
 path('site/profile-options/',Options.as_view()),
 path('members/me/cv-data/',cv.CVData.as_view()),path('members/me/cv.docx',cv.GenerateCV.as_view()),path('members/me/cv-template.docx',cv.BlankCV.as_view()),
 path('members/me/resume-submissions/',submissions.Submissions.as_view()),
 path('members/me/resume-submissions/<uuid:pk>/withdraw/',submissions.Withdraw.as_view()),
 path('members/resume-inbox/',submissions.Inbox.as_view()),
 path('members/resume-inbox/<uuid:pk>/',submissions.Inbox.as_view()),
 path('members/resume-inbox/<uuid:pk>/preview/',submissions.SubmissionPreview.as_view()),
 path('members/resume-inbox/<uuid:pk>/download/',submissions.SubmissionDownload.as_view()),
 path('admin/resume-submissions/',submissions.Inbox.as_view()),
 path('members/notifications/',submissions.Notifications.as_view()),
 path('members/notifications/<uuid:pk>/read/',submissions.ReadNotification.as_view()),
 path('public/home/',v.Home.as_view()),
 path('content/capabilities/',v.Capabilities.as_view()),
 path('content/items/',v.Items.as_view()),path('content/items/<uuid:pk>/',v.Item.as_view()),
 path('content/items/<uuid:pk>/history/',v.History.as_view()),path('content/items/<uuid:pk>/restore/',v.History.as_view()),
 path('content/items/<uuid:pk>/grants/',v.Grant.as_view()),
 path('content/items/<uuid:pk>/delete/',v.Delete.as_view()),path('content/items/<uuid:pk>/undelete/',v.Undelete.as_view()),
 path('members/directory/',v.Directory.as_view()),path('members/me/profile/',v.Profile.as_view()),
 path('members/<uuid:pk>/profile/',v.Profile.as_view()),
 path('members/me/history/',v.ProfileHistory.as_view()),path('members/me/restore/',v.ProfileHistory.as_view()),
 path('members/<uuid:pk>/history/',v.ProfileHistory.as_view()),path('members/<uuid:pk>/restore/',v.ProfileHistory.as_view()),
 path('members/me/resumes/<uuid:pk>/delete/',v.ResumeDelete.as_view()),
 path('members/me/resumes/',v.Resumes.as_view()),path('members/me/resumes/<uuid:pk>/',v.Resumes.as_view()),
 path('admin/members/<int:owner_id>/resumes/',v.Resumes.as_view()),
 re_path(r'^ai/imports/[^/]+/apply/$',v.Gone.as_view()),
 re_path(r'^review/.*$',v.Gone.as_view()),
 re_path(r'^members/applications/.*$',v.Gone.as_view()),
 re_path(r'^members/me/draft/(submit|withdraw)/$',v.Gone.as_view()),
 re_path(r'^content/revisions/[^/]+/(submit|withdraw|discard)/$',v.Gone.as_view()),
 re_path(r'^content/contributions/[^/]+/confirm/$',v.Gone.as_view()),
 re_path(r'^content/items/[^/]+/revisions/$',v.Gone.as_view()),
 re_path(r'^content/revisions/.*$',v.Gone.as_view()),
 re_path(r'^content/contributors/.*$',v.Gone.as_view()),
 re_path(r'^members/me/draft/.*$',v.Gone.as_view()),
 path('content/confirmations/',v.Gone.as_view()),
]
