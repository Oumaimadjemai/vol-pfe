from django.urls import path,include
from .views import *

from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [

    # AUTH
    path("login/", CustomTokenObtainPairView.as_view(), name="login"),
    path("refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("signup/", RegisterVoyageurView.as_view(), name="signup"),
    # In your auth service urls.py
    path('me/', MeView.as_view(), name='me'),
     path("voyageurs/", VoyageurListView.as_view(), name="voyageur-list"),
    path("voyageurs/<int:pk>/", VoyageurDetailView.as_view(), name="voyageur-detail"),
    path("voyageurs/by-user/<int:user_id>/", VoyageurByUserView.as_view(), name="voyageur-by-user"),
    path("voyageurs/<int:pk>/update/", VoyageurUpdateView.as_view(), name="voyageur-update"),
    path("voyageurs/<int:pk>/delete/", VoyageurDeleteView.as_view(), name="voyageur-delete"),
    # Passenger CRUD
    path("passengers/", PassengerListView.as_view()),
    path("passengers/create/", PassengerCreateView.as_view()),
    path("passengers/<int:pk>/", PassengerDetailView.as_view()),
    path("passengers/<int:pk>/update/", PassengerUpdateView.as_view()),
    path("passengers/<int:pk>/delete/", PassengerDeleteView.as_view()),
     path("passengers/by-voyageur/<int:voyageur_id>/", PassengerByVoyageurView.as_view(), name="passengers-by-voyageur"),
    # User CRUD (Admin)
    path("users/", UserListView.as_view()),
    path("users/create/", UserCreateView.as_view()),
    path("users/<int:pk>/", UserDetailView.as_view()),
    path("users/<int:pk>/update/", UserUpdateView.as_view()),
    path("users/<int:pk>/delete/", UserDeleteView.as_view()),

    # Password
    path('password-reset/', PasswordResetRequestView.as_view(), name='password_reset'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    
    # Change password (when logged in)
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),

    #  path('api/auth/', include('dj_rest_auth.urls')),  # login/logout/password
    path('api/auth/registration/', include('dj_rest_auth.registration.urls')),  # signup
    path('accounts/', include('allauth.urls')),  # for OAuth callbacks
     path("google-success/", GoogleSuccessView.as_view()),
]

# 