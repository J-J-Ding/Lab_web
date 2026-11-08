from django.urls import path

from . import views

urlpatterns = [
    path('auth/csrf/', views.CsrfView.as_view()),
    path('auth/register/', views.RegisterView.as_view()),
    path('auth/login/', views.LoginView.as_view()),
    path('auth/logout/', views.LogoutView.as_view()),
    path('auth/me/', views.MeView.as_view()),
    path('auth/change-password/', views.ChangePasswordView.as_view()),
    path('admin/usernames/available/',views.UsernameAvailableView.as_view()),
    path('admin/users/', views.UsersView.as_view()),
    path('admin/users/<int:pk>/', views.UserDetailView.as_view()),
    path('admin/users/<int:pk>/reset-password/', views.ResetPasswordView.as_view()),
]
