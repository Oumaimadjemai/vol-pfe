from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, role='voyageur'):
        if not email:
            raise ValueError("Email obligatoire")
        user = self.model(email=self.normalize_email(email), role=role)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password):
        user = self.create_user(email, password, role='admin')
        user.is_staff = True
        user.is_superuser = True
        user.save()
        return user


class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('agent', 'Agent'),
        ('voyageur', 'Voyageur'),
    )

    email = models.EmailField(unique=True)
    username = models.CharField(max_length=50)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    objects = UserManager()

    def __str__(self):
        return self.email

class Voyageur(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    nom = models.CharField(max_length=50)
    prenom = models.CharField(max_length=50)
    telephone = models.CharField(max_length=20)
    pays = models.CharField(max_length=50)
    num_passport = models.CharField(max_length=20)

class Passenger(models.Model):
    TYPE_CHOICES = (
        ('adulte', 'Adulte'),
        ('enfant', 'Enfant'),
    )

    voyageur = models.ForeignKey(
        Voyageur,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    type_passager = models.CharField(max_length=10, choices=TYPE_CHOICES)
