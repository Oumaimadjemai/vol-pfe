from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import authenticate

from .models import User, Voyageur, Passenger



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
        nom = validated_data.pop("nom")
        prenom = validated_data.pop("prenom")
        telephone = validated_data.pop("telephone")

        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            role="voyageur"
        )

        Voyageur.objects.create(
            user=user,
            nom=nom,
            prenom=prenom,
            telephone=telephone,
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



class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        validate_password(value)
        return value

    def validate(self, data):
        user = self.context["request"].user

        if not user.check_password(data["old_password"]):
            raise serializers.ValidationError(
                {"old_password": "Mot de passe incorrect"}
            )

        return data

    def save(self):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save()
        return user

class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        validate_password(value)
        return value

    def validate(self, data):
        email = data.get("email")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {"email": "Utilisateur introuvable"}
            )

        if user.is_blocked:
            raise serializers.ValidationError(
                {"email": "Compte bloqué"}
            )

        data["user"] = user
        return data

    def save(self):
        user = self.validated_data["user"]
        user.set_password(self.validated_data["new_password"])
        user.save()
        return user



class BlockUserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ["is_blocked"]
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate
from rest_framework import serializers


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = "identifier"

    identifier = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        identifier = attrs.get("identifier")
        password = attrs.get("password")

        user = authenticate(
            request=self.context.get("request"),
            username=identifier,
            password=password
        )

        if not user:
            raise serializers.ValidationError("Identifiants invalides")

        if user.is_blocked:
            raise serializers.ValidationError("Compte bloqué")

        refresh = self.get_token(user)

        response_data = {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "role": user.role,
            "email": user.email,
            "username": user.username,
        }

        # 🔥 If user is voyageur → add his info
        if user.role == "voyageur":
            try:
                voyageur = Voyageur.objects.get(user=user)

                response_data["voyageur"] = VoyageurSerializer(voyageur).data

            except Voyageur.DoesNotExist:
                response_data["voyageur"] = None

        return response_data