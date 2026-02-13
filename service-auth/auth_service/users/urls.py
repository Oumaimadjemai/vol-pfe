from django.urls import path
from .views import *

urlpatterns = [
    path('register/', RegisterView.as_view()),
    path('me/', ProfileView.as_view()),
    path('voyageurs/', VoyageurCreateView.as_view()),
    path('passengers/', PassengerCreateView.as_view()),
]
