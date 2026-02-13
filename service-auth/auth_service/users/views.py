from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import CustomTokenObtainPairSerializer
from .serializers import ResetPasswordSerializer


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import RegisterVoyageurSerializer


class RegisterVoyageurView(APIView):
    permission_classes = []

    def post(self, request):
        serializer = RegisterVoyageurSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": "Compte créé"}, status=status.HTTP_201_CREATED)

from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .models import Passenger
from .serializers import PassengerSerializer
from .permissions import IsVoyageur
class PassengerCreateView(generics.CreateAPIView):
    serializer_class = PassengerSerializer
    permission_classes = [IsAuthenticated, IsVoyageur]

class PassengerListView(generics.ListAPIView):
    serializer_class = PassengerSerializer
    permission_classes = [IsAuthenticated, IsVoyageur]

    def get_queryset(self):
        return Passenger.objects.filter(
            voyageur=self.request.user.voyageur
        )

class PassengerDetailView(generics.RetrieveAPIView):
    serializer_class = PassengerSerializer
    permission_classes = [IsAuthenticated, IsVoyageur]

    def get_queryset(self):
        return Passenger.objects.filter(
            voyageur=self.request.user.voyageur
        )
class PassengerUpdateView(generics.UpdateAPIView):
    serializer_class = PassengerSerializer
    permission_classes = [IsAuthenticated, IsVoyageur]

    def get_queryset(self):
        return Passenger.objects.filter(
            voyageur=self.request.user.voyageur
        )

class PassengerDeleteView(generics.DestroyAPIView):
    serializer_class = PassengerSerializer
    permission_classes = [IsAuthenticated, IsVoyageur]

    def get_queryset(self):
        return Passenger.objects.filter(
            voyageur=self.request.user.voyageur
        )
from .models import User
from .serializers import AdminCreateUserSerializer, UserSerializer
from .permissions import IsAdminOrAgent


class UserCreateView(generics.CreateAPIView):
    serializer_class = AdminCreateUserSerializer
    permission_classes = [IsAuthenticated, IsAdminOrAgent]

class UserListView(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdminOrAgent]
class UserDetailView(generics.RetrieveAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdminOrAgent]
class UserUpdateView(generics.UpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdminOrAgent]
class UserDeleteView(generics.DestroyAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdminOrAgent]


from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import ChangePasswordSerializer


class ChangePasswordView(generics.GenericAPIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = self.get_serializer(
            data=request.data,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": "Mot de passe changé"})




class ResetPasswordView(generics.GenericAPIView):
    serializer_class = ResetPasswordSerializer
    permission_classes = []

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": "Mot de passe réinitialisé"})
