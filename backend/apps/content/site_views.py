"""Session-aware website reads; anonymous public endpoints remain PUBLIC-only."""
from django.urls import path
from django.utils.cache import patch_vary_headers
from apps.accounts.authentication import VersionedSessionAuthentication
from . import public_views as public
from .direct_views import Home
from apps.assets.public_views import PublicAsset
from apps.analytics.views import PublicOverview,PublicAnnual
from .site_context import actor

class SiteMixin:
    authentication_classes=[VersionedSessionAuthentication]
    def dispatch(self,*args,**kwargs):
        token=actor.set(None)
        try:return super().dispatch(*args,**kwargs)
        finally:actor.reset(token)
    def initial(self,request,*args,**kwargs):
        super().initial(request,*args,**kwargs)
        actor.set(request.user)
    def finalize_response(self,request,response,*args,**kwargs):
        response=super().finalize_response(request,response,*args,**kwargs)
        response['Cache-Control']='private, no-store';patch_vary_headers(response,['Cookie'])
        return response

def view(cls):return type('Site'+cls.__name__,(SiteMixin,cls),{}).as_view()
urlpatterns=[path('site/legacy/',view(public.LegacyResolve)),path('site/home/',view(Home)),path('site/content/',view(public.ContentList)),path('site/content/<uuid:pk>/',view(public.ContentDetail)),path('site/members/',view(public.MemberList)),path('site/members/<str:slug>/',view(public.MemberDetail)),path('site/members/<str:slug>/achievements/',view(public.Achievements)),path('site/projects/<uuid:pk>/outputs/',view(public.Outputs)),path('site/graduates/',view(public.Graduates)),path('site/pages/<str:key>/',view(public.FixedPage)),path('site/assets/<uuid:pk>/',view(PublicAsset)),path('site/stats/annual/',view(PublicAnnual)),path('site/stats/overview/',view(PublicOverview))]
