from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import CustomTokenObtainPairSerializer
from .serializers import *


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


# views.py
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny


# views.py (your existing code)
class PasswordResetRequestView(generics.GenericAPIView):
    serializer_class = PasswordResetRequestSerializer
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()  # This will now send email via SMTP
        return Response(
            {"message": "Email de réinitialisation envoyé"},
            status=status.HTTP_200_OK
        )
class PasswordResetConfirmView(generics.GenericAPIView):
    """Step 2: Confirm password reset with token"""
    serializer_class = PasswordResetConfirmSerializer
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"message": "Mot de passe réinitialisé avec succès"},
            status=status.HTTP_200_OK
        )

class ChangePasswordView(generics.GenericAPIView):
    """Change password when already logged in"""
    serializer_class = ChangePasswordSerializer
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = self.get_serializer(
            data=request.data,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"message": "Mot de passe changé avec succès"},
            status=status.HTTP_200_OK
        )
# users/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.shortcuts import redirect
from django.conf import settings

        

# users/views.py
# class GoogleSuccessView(APIView):
#     permission_classes = []

#     def get(self, request):
#         if not request.user.is_authenticated:
#             return redirect(f"{settings.FRONTEND_URL}/signin")

#         refresh = RefreshToken.for_user(request.user)

#         voyageur = {
#             "nom": request.user.nom,
#             "prenom": request.user.prenom,
#         }

#         return redirect(
#             f"{settings.FRONTEND_URL}/auth/callback"
#             f"?access={str(refresh.access_token)}"
#             f"&refresh={str(refresh)}"
#             f"&voyageur={json.dumps(voyageur)}"
#         )

# users/views.py



from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.shortcuts import redirect
from django.conf import settings
import json
import urllib.parse

from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.shortcuts import redirect
from django.conf import settings
from allauth.socialaccount.models import SocialAccount
import json
import urllib.parse

class GoogleSuccessView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        print("="*50)
        print("GoogleSuccessView - GET request received")
        
        # Try to get user from session first
        if request.user.is_authenticated:
            user = request.user
            print(f"User authenticated via session: {user.email}")
        else:
            # If not authenticated via session, try to get the last social login
            # This is a workaround - get the most recent social account
            try:
                # This assumes the user just logged in with Google
                # You might need to pass the user ID via state parameter
                social_account = SocialAccount.objects.filter(provider='google').latest('id')
                user = social_account.user
                print(f"User found via social account: {user.email}")
            except SocialAccount.DoesNotExist:
                print("No social account found")
                return redirect("http://localhost:3000/login?error=no_user")
        
        print(f"User email: {user.email}")
        print(f"User ID: {user.id}")
        
        # Generate tokens
        refresh = RefreshToken.for_user(user)
        print(f"Access token generated: {str(refresh.access_token)[:20]}...")
        
        # Prepare user data
        user_data = {
            "id": user.id,
            "email": user.email,
            "nom": getattr(user, 'nom', ''),
            "prenom": getattr(user, 'prenom', ''),
            "role": getattr(user, 'role', 'voyageur')
        }
        print(f"User data: {user_data}")
        
        # Encode data
        user_data_json = json.dumps(user_data)
        encoded_user_data = urllib.parse.quote(user_data_json)
        
        # Build URL
        redirect_url = (
            f"http://localhost:3000/auth/callback"
            f"?access_token={refresh.access_token}"
            f"&refresh_token={refresh}"
            f"&voyageur={encoded_user_data}"
        )
        
        print(f"Full redirect URL: {redirect_url}")
        print("="*50)
        
        return redirect(redirect_url)