from rest_framework import generics, permissions
from .models import Voyageur, Passenger
from .serializers import (
    RegisterSerializer,
    UserSerializer,
    VoyageurSerializer,
    PassengerSerializer
)

class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class ProfileView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class VoyageurCreateView(generics.CreateAPIView):
    serializer_class = VoyageurSerializer
    permission_classes = [permissions.IsAuthenticated]


class PassengerCreateView(generics.CreateAPIView):
    serializer_class = PassengerSerializer
    permission_classes = [permissions.IsAuthenticated]
