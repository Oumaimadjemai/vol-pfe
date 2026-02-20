from django.urls import path,include
from .views import *

from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [

    # AUTH
    path("login/", CustomTokenObtainPairView.as_view(), name="login"),
    path("refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("signup/", RegisterVoyageurView.as_view(), name="signup"),

    # Passenger CRUD
    path("passengers/", PassengerListView.as_view()),
    path("passengers/create/", PassengerCreateView.as_view()),
    path("passengers/<int:pk>/", PassengerDetailView.as_view()),
    path("passengers/<int:pk>/update/", PassengerUpdateView.as_view()),
    path("passengers/<int:pk>/delete/", PassengerDeleteView.as_view()),

    # User CRUD (Admin)
    path("users/", UserListView.as_view()),
    path("users/create/", UserCreateView.as_view()),
    path("users/<int:pk>/", UserDetailView.as_view()),
    path("users/<int:pk>/update/", UserUpdateView.as_view()),
    path("users/<int:pk>/delete/", UserDeleteView.as_view()),

    # Password
    path("change-password/", ChangePasswordView.as_view()),
    path("reset-password/", ResetPasswordView.as_view()),

     path('api/auth/', include('dj_rest_auth.urls')),  # login/logout/password
    path('api/auth/registration/', include('dj_rest_auth.registration.urls')),  # signup
    path('accounts/', include('allauth.urls')),  # for OAuth callbacks
    #  path('api/auth/google/callback/', GoogleAuthCallbackView.as_view(), name='google_callback'),
     path("google-success/", GoogleSuccessView.as_view()),
]

# 