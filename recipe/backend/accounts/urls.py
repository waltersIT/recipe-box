from django.urls import path

from . import views

urlpatterns = [
    path("auth/me/", views.me, name="auth-me"),
    path("auth/register/", views.register, name="auth-register"),
    path("auth/login/", views.sign_in, name="auth-login"),
    path("auth/logout/", views.sign_out, name="auth-logout"),
    path("users/me/", views.update_me, name="user-update"),
    path("users/me/avatar/", views.avatar, name="user-avatar"),
    path("users/<str:username>/", views.profile_detail, name="user-detail"),
    path("users/<str:username>/recipes/", views.profile_recipes, name="user-recipes"),
    path("users/<str:username>/follow/", views.follow, name="user-follow"),
    path("users/<str:username>/following/", views.following_list, name="user-following"),
    path("users/<str:username>/followers/", views.follower_list, name="user-followers"),
]
