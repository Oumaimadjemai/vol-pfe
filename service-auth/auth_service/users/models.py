from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from datetime import date
class UserManager(BaseUserManager):
    def create_user(self, email, password=None, role='voyageur', **extra_fields):
        if not email:
            raise ValueError("Email obligatoire")
        user = self.model(email=self.normalize_email(email), role=role, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("role", "admin")
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('agent', 'Agent'),
        ('voyageur', 'Voyageur'),
    )

    email = models.EmailField(unique=True)
    username = models.CharField(max_length=50,unique=True,null=True,blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='voyageur')
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_blocked = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    objects = UserManager()

    def __str__(self):
        return self.email

class Personne(models.Model):
    SEXE_CHOICES = (
        ('homme', 'Homme'),
        ('femme', 'Femme'),
    )

    nom = models.CharField(max_length=50)
    prenom = models.CharField(max_length=50)
    date_naissance = models.DateField(null=True, blank=True)
    sexe = models.CharField(max_length=20, choices=SEXE_CHOICES)
    num_passport = models.CharField(max_length=20, blank=True)
    date_exp_passport = models.DateField(null=True, blank=True)
    class Meta:
        abstract = True

class Voyageur(Personne):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'voyageur'}
    )

    telephone = models.CharField(max_length=20)
    pays = models.CharField(max_length=50)
    wilaya = models.CharField(max_length=100)
    commune = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.nom} {self.prenom}"

class Passenger(Personne):
    TYPE_CHOICES = (
        ('adulte', 'Adulte'),
        ('enfant', 'Enfant'),
        ('bebe', 'Bébé'),
    )

    voyageur = models.ForeignKey(
        Voyageur,
        on_delete=models.CASCADE,
        related_name="passagers"
    )

    type_passager = models.CharField(max_length=10, choices=TYPE_CHOICES)
    def save(self, *args, **kwargs):
        if self.date_naissance:
            today = date.today()
            age = today.year - self.date_naissance.year-(
                (today.month,today.day)<(self.date_naissance.month,self.date_naissance.day)
            )
            if age < 2:
                self.type_passager = 'bebe'
            elif age < 12:
                self.type_passager = 'enfant'
            else:
                self.type_passager = 'adulte'

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nom} {self.prenom}"
