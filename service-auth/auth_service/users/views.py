from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import CustomTokenObtainPairSerializer
from .serializers import *


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import RegisterVoyageurSerializer
from kafka_utils import kafka
from django.utils import timezone

class RegisterVoyageurView(APIView):
    permission_classes = []

    def post(self, request):
        serializer = RegisterVoyageurSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        from .models import Voyageur
        voyageur=Voyageur.objects.get(user=user)
        kafka.send_event(
            topic='user-events',
            event_type='USER_REGISTERED',
            payload={
                'user_id': user.id,
                'email': user.email,
                'role': user.role,
                'username': user.username,
                'timestamp': timezone.now().isoformat()
            },
            source_service='auth-service'
        )
        kafka.send_event(
            topic='voyageur-events',
            event_type='VOYAGEUR_REGISTERED',
            payload={
                'voyageur_id': voyageur.id,
                'user_id': user.id,
                'nom':voyageur.nom,
                'prenom':voyageur.prenom,
                'email': user.email,
                'telephone': voyageur.telephone,
                'timestamp': timezone.now().isoformat()
            },
            source_service='auth-service'
        )

        return Response({"message": "Compte créé"}, status=status.HTTP_201_CREATED)
    

from rest_framework import generics
from rest_framework.permissions import IsAuthenticated,AllowAny
from .models import Voyageur
from .serializers import VoyageurSerializer
from .permissions import IsVoyageur, IsAdminOrAgent


class VoyageurListView(generics.ListAPIView):
    """
    List all voyageurs
    URL: /voyageurs/
    Accessible by: Admin/Agent only
    """
    queryset = Voyageur.objects.all()
    serializer_class = VoyageurSerializer
    permission_classes = [AllowAny]


class VoyageurDetailView(generics.RetrieveAPIView):
    """
    Get a specific voyageur by ID
    URL: /voyageurs/{id}/
    Accessible by: Admin/Agent or the voyageur themselves
    """
    queryset = Voyageur.objects.all()
    serializer_class = VoyageurSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        user = self.request.user
        voyageur_id = self.kwargs.get('pk')
        
        # Admin/Agent can see any voyageur
        if user.role in ['admin', 'agent']:
            return Voyageur.objects.all()
        
        # Voyageur can only see themselves
        if user.role == 'voyageur' and hasattr(user, 'voyageur'):
            if str(user.voyageur.id) == str(voyageur_id):
                return Voyageur.objects.filter(id=voyageur_id)
        
        return Voyageur.objects.none()


class VoyageurByUserView(generics.RetrieveAPIView):
    """
    Get voyageur by user ID
    URL: /voyageurs/by-user/{user_id}/
    Accessible by: Admin/Agent or the voyageur themselves
    """
    serializer_class = VoyageurSerializer
    permission_classes = [AllowAny]
    
    def get_object(self):
        user_id = self.kwargs.get('user_id')
        
        # Check permissions
        current_user = self.request.user
        
        # Admin/Agent can access any voyageur by user_id
        if current_user.role in ['admin', 'agent']:
            try:
                return Voyageur.objects.get(user_id=user_id)
            except Voyageur.DoesNotExist:
                from rest_framework.exceptions import NotFound
                raise NotFound("Voyageur not found for this user")
        
        # Voyageur can only access their own
        if current_user.role == 'voyageur' and current_user.id == int(user_id):
            try:
                return current_user.voyageur
            except Voyageur.DoesNotExist:
                from rest_framework.exceptions import NotFound
                raise NotFound("Voyageur profile not found")
        
        # If no permission
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied("You don't have permission to access this voyageur")


class VoyageurUpdateView(generics.UpdateAPIView):
    """
    Update a voyageur
    URL: /voyageurs/{id}/update/
    Accessible by: Admin/Agent or the voyageur themselves
    """
    serializer_class = VoyageurSerializer
    permission_classes = [IsAuthenticated]

    def perform_update(self, serializer):
        Voyageur = serializer.save()
        kafka.send_event(
            topic='voyageur-events',
            event_type='VOYAGEUR_UPDATED',
            payload={
                'voyageur_id': Voyageur.id,
                'user_id': Voyageur.user.id,
                'nom':Voyageur.nom,
                'prenom':Voyageur.prenom,
                'email': Voyageur.user.email,
                'telephone': Voyageur.telephone,
                'timestamp': timezone.now().isoformat()
            },
            source_service='auth-service'
        )
    
    def get_queryset(self):
        user = self.request.user
        voyageur_id = self.kwargs.get('pk')
        
        # Admin/Agent can update any voyageur
        if user.role in ['admin', 'agent']:
            return Voyageur.objects.all()
        
        # Voyageur can only update themselves
        if user.role == 'voyageur' and hasattr(user, 'voyageur'):
            if str(user.voyageur.id) == str(voyageur_id):
                return Voyageur.objects.filter(id=voyageur_id)
        
        return Voyageur.objects.none()


class VoyageurDeleteView(generics.DestroyAPIView):
    """
    Delete a voyageur
    URL: /voyageurs/{id}/delete/
    Accessible by: Admin/Agent only
    """
    queryset = Voyageur.objects.all()
    serializer_class = VoyageurSerializer
    permission_classes = [IsAuthenticated, IsAdminOrAgent]
    
    def perform_destroy(self, instance):
        # This will delete both the voyageur and the associated user
        # because of the CASCADE on the OneToOneField
        user = instance.user
        instance.delete()
        user.delete()

from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .models import Passenger
from .serializers import PassengerSerializer
from .permissions import IsVoyageur
class PassengerCreateView(generics.CreateAPIView):
    serializer_class = PassengerSerializer
    permission_classes = [IsAuthenticated]
    def perform_create(self, serializer):
        passenger = serializer.save()
        kafka.send_event(
            topic='passenger-events',
            event_type='PASSENGER_CREATED',
            payload={
                'passenger_id': passenger.id,
                'voyageur_id': passenger.voyageur.id,
                'nom': passenger.nom,
                'prenom': passenger.prenom,
                'date_naissance': passenger.date_naissance.isoformat(),
                'timestamp': timezone.now().isoformat()
            },
            source_service='auth-service'
        )   

class PassengerListView(generics.ListAPIView):
    serializer_class = PassengerSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Passenger.objects.filter(
            voyageur=self.request.user.voyageur
        )

# users/views.py

class PassengerDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Passenger.objects.all()
    serializer_class = PassengerSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        # Vérifier si l'utilisateur est admin
        is_admin = False
        if hasattr(user, 'is_staff') and user.is_staff:
            is_admin = True
        elif hasattr(user, 'is_superuser') and user.is_superuser:
            is_admin = True
        elif hasattr(user, 'role') and user.role == 'admin':
            is_admin = True
        
        # Les admins voient tous les passagers
        if is_admin:
            return Passenger.objects.all()
        
        # Les utilisateurs normaux voient seulement leurs passagers
        if hasattr(user, 'voyageur') and user.voyageur:
            return Passenger.objects.filter(voyageur=user.voyageur)
        
        # Si l'utilisateur n'a pas de voyageur, retourner vide
        return Passenger.objects.none()
class PassengerUpdateView(generics.UpdateAPIView):
    serializer_class = PassengerSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Passenger.objects.filter(
            voyageur=self.request.user.voyageur
        )
    def perform_update(self, serializer):
        passenger = serializer.save()
        kafka.send_event(
            topic='passenger-events',
            event_type='PASSENGER_UPDATED',
            payload={
                'passenger_id': passenger.id,
                'voyageur_id': passenger.voyageur.id,
                'nom': passenger.nom,
                'prenom': passenger.prenom,
                'date_naissance': passenger.date_naissance.isoformat(),
                'timestamp': timezone.now().isoformat()
            },
            source_service='auth-service'
        )

class PassengerDeleteView(generics.DestroyAPIView):
    serializer_class = PassengerSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Passenger.objects.filter(
            voyageur=self.request.user.voyageur
        )
    def perform_destroy(self, instance):
        passenger_id = instance.id
        voyageur_id = instance.voyageur.id
        instance.delete()
        kafka.send_event(
            topic='passenger-events',
            event_type='PASSENGER_DELETED',
            payload={
                'passenger_id': passenger_id,
                'voyageur_id': voyageur_id,
                'timestamp': timezone.now().isoformat()
            },
            source_service='auth-service'
        )

from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .models import Passenger
from .serializers import PassengerSerializer
from .permissions import IsVoyageur, IsAdminOrAgent


# Existing Passenger views...

class PassengerByVoyageurView(generics.ListAPIView):
    """
    Get all passengers for a specific voyageur
    URL: /passengers/by-voyageur/{voyageur_id}/
    Accessible by: Voyageur (own) or Admin/Agent (all)
    """
    serializer_class = PassengerSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        voyageur_id = self.kwargs.get('voyageur_id')
        
        # Check permissions
        user = self.request.user
        
        # If user is admin or agent, they can access any voyageur's passengers
        if user.role in ['admin', 'agent']:
            return Passenger.objects.filter(voyageur_id=voyageur_id)
        
        # If user is voyageur, they can only access their own passengers
        if user.role == 'voyageur' and hasattr(user, 'voyageur') and user.voyageur.id == voyageur_id:
            return Passenger.objects.filter(voyageur_id=voyageur_id)
        
        # If no permission, return empty queryset
        return Passenger.objects.none()
# views.py - Mise à jour des vues utilisateur
from .serializers import AdminCreateUserSerializer, UserSerializer, UserUpdateSerializer

class UserCreateView(generics.CreateAPIView):
    serializer_class = AdminCreateUserSerializer
    permission_classes = [IsAuthenticated, IsAdminOrAgent]
    def perform_create(self, serializer):
        user = serializer.save()
        kafka.send_event(
            topic='user-events',
            event_type='USER_CREATED',
            payload={
                'user_id': user.id,
                'email': user.email,
                'role': user.role,
                'username': user.username,
                'is_active': user.is_active,
                'is_blocked': user.is_blocked,
                'status': user.status,
                'timestamp': timezone.now().isoformat()
            },
            source_service='auth-service'
        )

class UserListView(generics.ListAPIView):
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdminOrAgent]

class UserDetailView(generics.RetrieveAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdminOrAgent]

class UserUpdateView(generics.UpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserUpdateSerializer
    permission_classes = [IsAuthenticated, IsAdminOrAgent]
    def perform_update(self, serializer):
        user = serializer.save()
        kafka.send_event(
            topic='user-events',
            event_type='USER_UPDATED',
            payload={
                'user_id': user.id,
                'email': user.email,
                'role': user.role,
                'username': user.username,
                'is_active': user.is_active,
                'is_blocked': user.is_blocked,
                'status': user.status,
                'timestamp': timezone.now().isoformat()
            },
            source_service='auth-service'
        )


class UserDeleteView(generics.DestroyAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdminOrAgent]
    def perform_destroy(self, instance):
        user_id = instance.id
        instance.delete()
        kafka.send_event(
            topic='user-events',
            event_type='USER_DELETED',
            payload={
                'user_id': user_id,
                'email': instance.email,
                'role': instance.role,
                'timestamp': timezone.now().isoformat()
            },
            source_service='auth-service'
        )

# Ajout d'une vue pour mettre à jour les features d'un agent
class UserFeaturesUpdateView(generics.UpdateAPIView):
    queryset = User.objects.filter(role='agent')
    serializer_class = UserUpdateSerializer
    permission_classes = [IsAuthenticated, IsAdminOrAgent]
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data={'features': request.data.get('features', [])}, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

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
        kafka.send_event(
            topic='user-events',
            event_type='PASSWORD_RESET_REQUESTED',
            payload={
                'email': serializer.validated_data['email'],
                'timestamp': timezone.now().isoformat() 
            },
            source_service='auth-service'   
        )
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
        kafka.send_event(
            topic='user-events',
            event_type='PASSWORD_RESET_CONFIRMED',
            payload={
                'email': serializer.validated_data['email'],
                'timestamp': timezone.now().isoformat() ,
            },
            source_service='auth-service'   
        )
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
    

# In your auth service (service 1) - add this view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import UserSerializer, VoyageurSerializer

# Mise à jour de MeView
class MeView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        data = {
            'id': user.id,
            'email': user.email,
            'username': user.username,
            'role': user.role,
            'is_active': user.is_active,
            'is_blocked': user.is_blocked,
            'status': user.status,
            'date_joined': user.date_joined.strftime("%Y-%m-%d"),
            'last_login': user.last_login.strftime("%Y-%m-%d") if user.last_login else None,
            'features': user.features if user.role == 'agent' else [],
        }
        
        # Add voyageur data if role is voyageur
        if user.role == 'voyageur' and hasattr(user, 'voyageur'):
            data['voyageur'] = VoyageurSerializer(user.voyageur).data
        
        return Response(data)   


# views.py (add these two views)
from .serializers import PassportUploadSerializer


class VoyageurPassportUploadView(generics.UpdateAPIView):
    """
    POST /voyageurs/{id}/passport/
    Voyageur uploads their own passport image → MRZ extracted & validated.
    """
    serializer_class = PassportUploadSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['patch', 'put']

    def get_object(self):
        user = self.request.user
        # Voyageur can only upload for themselves; admin can upload for anyone
        if user.role in ['admin', 'agent']:
            return generics.get_object_or_404(Voyageur, pk=self.kwargs['pk'])
        return generics.get_object_or_404(
            Voyageur, pk=self.kwargs['pk'], user=user
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.update(instance, serializer.validated_data)
        return Response(
            {
                'message': 'Passport vérifié avec succès.',
                'passport_verified': instance.passport_verified,
                'passport_verified_at': instance.passport_verified_at,
            },
            status=status.HTTP_200_OK
        )


class PassengerPassportUploadView(generics.UpdateAPIView):
    """
    PATCH /passengers/{id}/passport/
    Upload & validate a passport for a specific Passenger.
    """
    serializer_class = PassportUploadSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['patch', 'put']

    def get_object(self):
        user = self.request.user
        if user.role in ['admin', 'agent']:
            return generics.get_object_or_404(Passenger, pk=self.kwargs['pk'])
        return generics.get_object_or_404(
            Passenger, pk=self.kwargs['pk'], voyageur=user.voyageur
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.update(instance, serializer.validated_data)
        return Response(
            {
                'message': 'Passport passager vérifié avec succès.',
                'passport_verified': instance.passport_verified,
                'passport_verified_at': instance.passport_verified_at,
            },
            status=status.HTTP_200_OK
        )