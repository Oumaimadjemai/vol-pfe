# serializers.py - Version complète et corrigée
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import authenticate
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.conf import settings

from .models import User, Voyageur, Passenger

User = get_user_model()

# ==================== REGISTER SERIALIZERS ====================

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
    identifier = serializers.CharField()
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

# ==================== USER SERIALIZERS ====================

class UserSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    date_joined_formatted = serializers.SerializerMethodField()
    last_login_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "username",
            "role",
            "is_active",
            "is_blocked",
            "status",
            "date_joined",
            "date_joined_formatted",
            "last_login",
            "last_login_formatted",
            "updated_at",
            "features",
        ]
        read_only_fields = ["id", "date_joined", "updated_at"]
    
    def get_status(self, obj):
        if obj.is_blocked:
            return "Suspendu"
        if not obj.is_active:
            return "Inactif"
        return "Actif"
    
    def get_date_joined_formatted(self, obj):
        return obj.date_joined.strftime("%Y-%m-%d") if obj.date_joined else None
    
    def get_last_login_formatted(self, obj):
        return obj.last_login.strftime("%Y-%m-%d") if obj.last_login else None

class AdminCreateUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    status = serializers.ChoiceField(
        choices=['active', 'inactive', 'suspended'],
        write_only=True,
        required=False,
        default='active'
    )
    
    class Meta:
        model = User
        fields = ["email", "username", "password", "role", "status", "features"]
    
    def validate_password(self, value):
        validate_password(value)
        return value
    
    def validate_features(self, value):
        role = self.initial_data.get('role')
        # Filtrer les valeurs null
        if value:
            value = [f for f in value if f and f is not None]
        if role == 'agent' and (not value or len(value) == 0):
            raise serializers.ValidationError("Les agents doivent avoir au moins une fonctionnalité")
        return value
    
    def create(self, validated_data):
        status_value = validated_data.pop('status', 'active')
        features = validated_data.pop('features', [])
        # Filtrer les valeurs null
        features = [f for f in features if f and f is not None]
        password = validated_data.pop("password")
        role = validated_data.get("role")
        
        user = User(**validated_data)
        user.set_password(password)
        user.features = features
        
        if status_value == 'suspended':
            user.is_blocked = True
            user.is_active = False
        elif status_value == 'inactive':
            user.is_blocked = False
            user.is_active = False
        else:
            user.is_blocked = False
            user.is_active = True
        
        user.save()
        
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
class UserUpdateSerializer(serializers.ModelSerializer):
    status = serializers.ChoiceField(
        choices=['active', 'inactive', 'suspended'],
        write_only=True,
        required=False
    )
    
    class Meta:
        model = User
        fields = ["email", "username", "role", "is_active", "is_blocked", "status", "features"]
    
    def update(self, instance, validated_data):
        status_value = validated_data.pop('status', None)
        
        if status_value:
            if status_value == 'suspended':
                instance.is_blocked = True
                instance.is_active = False
            elif status_value == 'inactive':
                instance.is_blocked = False
                instance.is_active = False
            else:
                instance.is_blocked = False
                instance.is_active = True
        
        # Gérer spécifiquement les features
        if 'features' in validated_data:
            features = validated_data.pop('features')
            # Filtrer les valeurs null et vides
            instance.features = [f for f in features if f and f is not None]
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance
# ==================== JWT SERIALIZER ====================

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
            "status": "Actif" if user.is_active and not user.is_blocked else "Suspendu" if user.is_blocked else "Inactif",
            "date_joined": user.date_joined.strftime("%Y-%m-%d") if user.date_joined else None,
            "features": user.features if user.role == 'agent' else [],
        }

        if user.role == "voyageur":
            voyageur = getattr(user, "voyageur", None)
            data["voyageur"] = (
                VoyageurSerializer(voyageur).data if voyageur else None
            )

        return data

# ==================== VOYAGEUR SERIALIZERS ====================

# serializers.py - Corrected VoyageurSerializer

class VoyageurSerializer(serializers.ModelSerializer):
    """Basic Voyageur serializer with user email"""
    email = serializers.EmailField(source='user.email', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    user_status = serializers.SerializerMethodField()
    passport_image = serializers.ImageField(read_only=True)
    
    class Meta:
        model = Voyageur
        # Use only 'fields' OR 'exclude', not both
        fields = [
            'id', 'email', 'username', 'user_status',
            'nom', 'prenom', 'date_naissance', 'sexe', 'telephone',
            'pays', 'wilaya', 'commune', 'num_passport', 'date_exp_passport','passport_image','passport_verified','passport_verified_at'
        ]
    
    def get_user_status(self, obj):
        if obj.user.is_blocked:
            return "suspended"
        if not obj.user.is_active:
            return "inactive"
        return "active"
class VoyageurDetailSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)
    user_is_active = serializers.BooleanField(source='user.is_active', read_only=True)
    user_is_blocked = serializers.BooleanField(source='user.is_blocked', read_only=True)
    
    class Meta:
        model = Voyageur
        fields = [
            'id', 'user', 'user_email', 'user_username', 'user_is_active', 'user_is_blocked',
            'nom', 'prenom', 'date_naissance', 'sexe', 'telephone',
            'pays', 'wilaya', 'commune', 'num_passport', 'date_exp_passport',
        ]
        read_only_fields = ['id']

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

# ==================== PASSENGER SERIALIZERS ====================

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

# ==================== PASSWORD SERIALIZERS ====================

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    
    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Aucun utilisateur avec cet email")
        return value
    
    def save(self):
        email = self.validated_data['email']
        user = User.objects.get(email=email)
        
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        
        reset_link = f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}/"
        
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


# serializers.py (add at bottom)
from django.utils import timezone
from .passport_service import _parse_mrz_date, extract_mrz_data, validate_mrz_against_person


class PassportUploadSerializer(serializers.Serializer):
    """
    Works for both Voyageur and Passenger.
    Pass the Personne subclass instance as the object to update.
    """
    passport_image = serializers.ImageField()

    def update(self, instance, validated_data):
        # 1. Save image to Cloudinary
        instance.passport_image = validated_data['passport_image']
        instance.passport_verified = False          # reset until re-validated
        instance.passport_verified_at = None
        instance.save()

        # 2. Extract MRZ from the now-stored Cloudinary URL
        image_url = instance.passport_image.url
        mrz_data = extract_mrz_data(image_url)

        if mrz_data is None:
            raise serializers.ValidationError({
                'passport_image': (
                    "Impossible de lire le MRZ. "
                    "Vérifiez que l'image est nette et que le bas du passeport est visible."
                )
            })

        # 3. Validate extracted data against model fields
        is_valid, errors = validate_mrz_against_person(instance, mrz_data)

        if not is_valid:
            raise serializers.ValidationError({'mrz_validation': errors})

        # 4. Mark as verified + sync any auto-filled fields (e.g. date_exp_passport)
        instance.passport_verified = True
        instance.passport_verified_at = timezone.now()
        instance.save()

        return instance
    

# Add to serializers.py

class VoyageurPassportSerializer(serializers.Serializer):
    """Serializer for voyageur passport upload with MRZ validation"""
    passport_image = serializers.ImageField()
    
    def update(self, instance, validated_data):
        # Save image to Cloudinary
        instance.passport_image = validated_data['passport_image']
        instance.passport_verified = False
        instance.passport_verified_at = None
        instance.save()
        
        # Extract MRZ from the stored Cloudinary URL
        image_url = instance.passport_image.url
        print(f"[Passport] Processing image URL: {image_url}")
        
        mrz_data = extract_mrz_data(image_url)
        
        if mrz_data is None:
            raise serializers.ValidationError({
                'passport_image': (
                    "Impossible de lire le MRZ. Vérifiez que l'image est nette "
                    "et que le bas du passeport est visible. Assurez-vous que "
                    "la photo est bien cadrée sur la zone MRZ (en bas du passeport)."
                )
            })
        
        # Validate against person data
        is_valid, errors = validate_mrz_against_person(instance, mrz_data)
        
        if not is_valid:
            raise serializers.ValidationError({'mrz_validation': errors})
        
        # Mark as verified
        instance.passport_verified = True
        instance.passport_verified_at = timezone.now()
        instance.save()
        
        return instance


class PassengerPassportSerializer(serializers.Serializer):
    """Serializer for passenger passport upload with MRZ validation"""
    passport_image = serializers.ImageField()
    
    def update(self, instance, validated_data):
        # Save image to Cloudinary
        instance.passport_image = validated_data['passport_image']
        instance.passport_verified = False
        instance.passport_verified_at = None
        instance.save()
        
        # Extract MRZ
        image_url = instance.passport_image.url
        print(f"[Passport] Processing passenger image URL: {image_url}")
        
        mrz_data = extract_mrz_data(image_url)
        
        if mrz_data is None:
            raise serializers.ValidationError({
                'passport_image': (
                    "Impossible de lire le MRZ. Vérifiez que l'image est nette "
                    "et que le bas du passeport est visible."
                )
            })
        
        # Auto-fill fields from MRZ if they're empty
        if not instance.num_passport and mrz_data.get('number'):
            instance.num_passport = mrz_data.get('number')
        
        if not instance.date_naissance and mrz_data.get('date_of_birth'):
            dob = _parse_mrz_date(mrz_data['date_of_birth'])
            if dob:
                instance.date_naissance = dob
        
        if not instance.date_exp_passport and mrz_data.get('expiry_date'):
            expiry = _parse_mrz_date(mrz_data['expiry_date'])
            if expiry:
                instance.date_exp_passport = expiry
        
        if not instance.nom and mrz_data.get('surname'):
            instance.nom = mrz_data.get('surname')
        
        if not instance.prenom and mrz_data.get('name'):
            instance.prenom = mrz_data.get('name')
        
        # Validate
        is_valid, errors = validate_mrz_against_person(instance, mrz_data)
        
        if not is_valid:
            raise serializers.ValidationError({'mrz_validation': errors})
        
        # Mark as verified
        instance.passport_verified = True
        instance.passport_verified_at = timezone.now()
        instance.save()
        
        return instance