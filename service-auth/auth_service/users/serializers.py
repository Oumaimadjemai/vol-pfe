from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import authenticate

from .models import User, Voyageur, Passenger



# class RegisterVoyageurSerializer(serializers.Serializer):
#     email = serializers.EmailField()
#     password = serializers.CharField(write_only=True)

#     nom = serializers.CharField()
#     prenom = serializers.CharField()
#     telephone = serializers.CharField()

#     def validate_password(self, value):
#         validate_password(value)
#         return value
    
#     def validate_email(self, value):
#       if User.objects.filter(email=value).exists():
#         raise serializers.ValidationError("Email déjà utilisé")
#       return value


#     def create(self, validated_data):
#         nom = validated_data.pop("nom")
#         prenom = validated_data.pop("prenom")
#         telephone = validated_data.pop("telephone")

#         user = User.objects.create_user(
#             email=validated_data["email"],
#             password=validated_data["password"],
#             role="voyageur"
#         )

#         Voyageur.objects.create(
#             user=user,
#             nom=nom,
#             prenom=prenom,
#             telephone=telephone,
#             pays="",
#             wilaya="",
#             commune=""
#         )

#         return user

class RegisterVoyageurSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    nom = serializers.CharField()
    prenom = serializers.CharField()
    telephone = serializers.CharField()

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email déjà utilisé")
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            role="voyageur"
        )

        Voyageur.objects.create(
            user=user,
            nom=validated_data["nom"],
            prenom=validated_data["prenom"],
            telephone=validated_data["telephone"],
            pays="",
            wilaya="",
            commune=""
        )

        return user

class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField()  # email OR username
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(
            username=data["identifier"],
            password=data["password"]
        )

        if not user:
            raise serializers.ValidationError("Identifiants invalides")

        if user.is_blocked:
            raise serializers.ValidationError("Compte bloqué")

        data["user"] = user
        return data



class AdminCreateUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["email", "username", "password", "role"]

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        role = validated_data.get("role")

        user = User(**validated_data)
        user.set_password(password)
        user.save()

        # 🔥 AUTO CREATE VOYAGEUR IF ROLE = voyageur
        if role == "voyageur":
            Voyageur.objects.create(
                user=user,
                nom="",
                prenom="",
                telephone="",
                pays="",
                wilaya="",
                commune=""
            )

        return user



class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "username",
            "role",
            "is_active",
            "is_blocked"
        ]
        read_only_fields = fields



class VoyageurSerializer(serializers.ModelSerializer):
    class Meta:
        model = Voyageur
        exclude = ["user"]

class VoyageurSignupSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True)

    class Meta:
        model = Voyageur
        fields = [
            "email",
            "password",
            "nom",
            "prenom",
            "telephone",
            "pays",
            "wilaya",
            "commune",
            "sexe"
        ]

    def create(self, validated_data):
        email = validated_data.pop("email")
        password = validated_data.pop("password")

        user = User.objects.create_user(
            email=email,
            password=password,
            role="voyageur"
        )

        voyageur = Voyageur.objects.create(
            user=user,
            **validated_data
        )

        return voyageur

class PassengerSerializer(serializers.ModelSerializer):

    class Meta:
        model = Passenger
        exclude = ["voyageur", "type_passager"]
        read_only_fields = ["type_passager"]

    def create(self, validated_data):
        user = self.context["request"].user
        voyageur = user.voyageur

        return Passenger.objects.create(
            voyageur=voyageur,
            **validated_data
        )



# serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.conf import settings

User = get_user_model()

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    
    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Aucun utilisateur avec cet email")
        return value
    
    def save(self):
        email = self.validated_data['email']
        user = User.objects.get(email=email)
        
        # Generate token
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        
        # Create reset link (frontend URL)
        reset_link = f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}/"
        
        # Send email
        send_mail(
            'Réinitialisation de votre mot de passe',
            f'Cliquez sur ce lien pour réinitialiser votre mot de passe: {reset_link}',
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
        return user

class PasswordResetConfirmSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)
    uid = serializers.CharField()
    token = serializers.CharField()
    
    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError("Les mots de passe ne correspondent pas")
        
        try:
            uid = force_str(urlsafe_base64_decode(data['uid']))
            self.user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError("Lien de réinitialisation invalide")
        
        if not default_token_generator.check_token(self.user, data['token']):
            raise serializers.ValidationError("Lien de réinitialisation invalide ou expiré")
        
        return data
    
    def save(self):
        self.user.set_password(self.validated_data['password'])
        self.user.save()
        return self.user

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(write_only=True, min_length=8)
    
    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Ancien mot de passe incorrect")
        return value
    
    def validate(self, data):
        if data['new_password'] != data['new_password_confirm']:
            raise serializers.ValidationError("Les nouveaux mots de passe ne correspondent pas")
        return data
    
    def save(self):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user

class BlockUserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ["is_blocked"]
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate
from rest_framework import serializers


# class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
#     username_field = "identifier"

#     identifier = serializers.CharField()
#     password = serializers.CharField(write_only=True)

#     def validate(self, attrs):
#         identifier = attrs.get("identifier")
#         password = attrs.get("password")

#         user = authenticate(
#             request=self.context.get("request"),
#             username=identifier,
#             password=password
#         )

#         if not user:
#             raise serializers.ValidationError("Identifiants invalides")

#         if user.is_blocked:
#             raise serializers.ValidationError("Compte bloqué")

#         refresh = self.get_token(user)

#         response_data = {
#             "refresh": str(refresh),
#             "access": str(refresh.access_token),
#             "role": user.role,
#             "email": user.email,
#             "username": user.username,
#         }

#         # 🔥 If user is voyageur → add his info
#         if user.role == "voyageur":
#             try:
#                 voyageur = Voyageur.objects.get(user=user)

#                 response_data["voyageur"] = VoyageurSerializer(voyageur).data

#             except Voyageur.DoesNotExist:
#                 response_data["voyageur"] = None

#         return response_data
    

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = "identifier"

    identifier = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get("request"),
            username=attrs.get("identifier"),
            password=attrs.get("password")
        )

        if not user:
            raise serializers.ValidationError("Identifiants invalides")

        if user.is_blocked:
            raise serializers.ValidationError("Compte bloqué")

        refresh = self.get_token(user)

        data = {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "role": user.role,
            "email": user.email,
            "username": user.username,
        }

        if user.role == "voyageur":
            voyageur = getattr(user, "voyageur", None)
            data["voyageur"] = (
                VoyageurSerializer(voyageur).data if voyageur else None
            )

        return data