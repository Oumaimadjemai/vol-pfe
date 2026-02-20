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

# users/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.shortcuts import redirect
from django.conf import settings

class GoogleAuthCallbackView(APIView):
    permission_classes = []  # Permet l'accès sans authentification
    
    def get(self, request):
        # Cette vue reçoit le callback après l'auth Google
        frontend_url = request.GET.get('frontend', settings.FRONTEND_URL)
        
        # Vérifier si l'utilisateur est authentifié
        if request.user.is_authenticated:
            # Générer les tokens JWT
            refresh = RefreshToken.for_user(request.user)
            
            # Rediriger vers le frontend avec les tokens
            redirect_url = f"{frontend_url}/auth/callback?access_token={str(refresh.access_token)}&refresh_token={str(refresh)}"
            return redirect(redirect_url)
        else:
            return redirect(f"{frontend_url}/signin?error=auth_failed")
        

# users/views.py
class GoogleSuccessView(APIView):
    permission_classes = []

    def get(self, request):
        if not request.user.is_authenticated:
            return redirect(f"{settings.FRONTEND_URL}/signin")

        refresh = RefreshToken.for_user(request.user)

        voyageur = {
            "nom": request.user.nom,
            "prenom": request.user.prenom,
        }

        return redirect(
            f"{settings.FRONTEND_URL}/auth/callback"
            f"?access={str(refresh.access_token)}"
            f"&refresh={str(refresh)}"
            f"&voyageur={json.dumps(voyageur)}"
        )