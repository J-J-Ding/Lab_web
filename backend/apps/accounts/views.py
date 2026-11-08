from django.db import DatabaseError
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework.exceptions import NotFound, PermissionDenied, Throttled, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .permissions import IsRoot
from .serializers import (AdminCreateSerializer, AdminUpdateSerializer, ChangePasswordSerializer,
                          LoginSerializer, PasswordSerializer, ProfileSerializer, RegisterSerializer,
                          StrictSerializer, UserSerializer)
from .throttling import consume_account, consume_ip


def csrf_failure(request, reason=''):
    return JsonResponse({'code': 'csrf_failed', 'detail': 'CSRF verification failed.', 'fields': {}}, status=403)


def validated(serializer_class, request):
    serializer = serializer_class(data=request.data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


@method_decorator(csrf_protect, name='dispatch')
class AccountAPIView(APIView):
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'no-store'
        return response

    def handle_exception(self, exc):
        try:
            if isinstance(exc, Throttled):
                services.audit('auth.login', request=self.request, outcome='throttled')
            elif self.request.path.startswith('/api/admin/') and getattr(self.request.user, 'is_authenticated', False) and isinstance(exc, (PermissionDenied, ValidationError, NotFound, Http404)):
                target_id = self.kwargs.get('pk')
                if target_id is not None and not 0 < target_id < 2**63:
                    target_id = None
                services.audit('management.denied', request=self.request, outcome='denied', actor_snapshot=self.request.user.pk, target_snapshot=target_id)
            if isinstance(exc, DatabaseError):
                return Response({'detail': 'Service temporarily unavailable.'}, status=503)
            return super().handle_exception(exc)
        except DatabaseError:
            return Response({'detail': 'Service temporarily unavailable.'}, status=503)


@method_decorator(ensure_csrf_cookie, name='dispatch')
class CsrfView(AccountAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    http_method_names = ['get']

    def get(self, request):
        return Response({'detail': 'CSRF cookie set'})


class RegisterView(AccountAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    http_method_names = ['post']

    def post(self, request):
        user = services.create_user(validated(RegisterSerializer, request), request)
        return Response(UserSerializer(user).data, status=201)


class LoginView(AccountAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    http_method_names = ['post']

    def check_throttles(self, request):
        consume_ip(request)

    def post(self, request):
        data = validated(LoginSerializer, request)
        consume_account(request, data['username'])
        user = services.login_user(request, data)
        if user is None:
            raise ValidationError({'detail': 'Invalid username or password.'})
        return Response(UserSerializer(user).data)


class LogoutView(AccountAPIView):
    http_method_names = ['post']

    def post(self, request):
        validated(StrictSerializer, request)
        services.logout_user(request)
        return Response(status=204)


class MeView(AccountAPIView):
    http_method_names = ['get', 'patch']

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        user = services.update_profile(request, validated(ProfileSerializer, request))
        return Response(UserSerializer(user).data)


class ChangePasswordView(AccountAPIView):
    http_method_names = ['post']

    def post(self, request):
        services.change_password(request, validated(ChangePasswordSerializer, request))
        return Response(status=204)


class UserPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = 'page_size'
    max_page_size = 100


class UsersView(AccountAPIView):
    permission_classes = [IsRoot]
    http_method_names = ['get', 'post']

    def get(self, request):
        paginator = UserPagination()
        from django.db.models import Q
        users=services.visible_users(request.user)
        state=request.query_params.get('state','active')
        if state not in ('active','cancelled'):raise ValidationError({'state':'无效账号状态。'})
        users=users.filter(is_active=state=='active')
        q=request.query_params.get('q','').strip()
        if len(q)>100:raise ValidationError({'q':'搜索内容不得超过100字。'})
        if q:users=users.filter(Q(username__icontains=q)|Q(first_name__icontains=q)|Q(last_name__icontains=q)|Q(member_profile__published_revision__display_name__icontains=q)|Q(member_profile__published_revision__isnull=True,member_profile__draft_revision__display_name__icontains=q)).distinct()
        users=users.select_related('member_profile__published_revision__avatar_asset','member_profile__draft_revision__avatar_asset')
        page = paginator.paginate_queryset(users, request)
        return paginator.get_paginated_response(UserSerializer(page, many=True).data)

    def post(self, request):
        user = services.create_user(validated(AdminCreateSerializer, request), request, managed=True)
        return Response(UserSerializer(user).data, status=201)


class UserDetailView(AccountAPIView):
    permission_classes = [IsRoot]
    http_method_names = ['get', 'patch']

    def get(self, request, pk):
        user = get_object_or_404(services.visible_users(request.user), pk=pk)
        return Response(UserSerializer(user).data)

    def patch(self, request, pk):
        user = services.manage_user(request, pk, validated(AdminUpdateSerializer, request))
        return Response(UserSerializer(user).data)


class ResetPasswordView(AccountAPIView):
    permission_classes = [IsRoot]
    http_method_names = ['post']

    def post(self, request, pk):
        services.manage_user(request, pk, validated(PasswordSerializer, request), reset_password=True)
        return Response(status=204)


class UsernameAvailableView(AccountAPIView):
    permission_classes=[IsRoot]
    http_method_names=['get']
    def get(self,request):
        from .models import User
        from .serializers import RegisterSerializer
        name=request.query_params.get('username','').strip()
        RegisterSerializer().validate_username(name)
        return Response({'available':True,'username':name})
