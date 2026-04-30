from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator

class Destination(models.Model):
    # Basic Information
    name = models.CharField(max_length=200, verbose_name="Nom")
    description = models.TextField(verbose_name="Description")
    country = models.CharField(max_length=100, verbose_name="Pays")
    city = models.CharField(max_length=100, verbose_name="Ville")
    continent = models.CharField(max_length=100, verbose_name="Continent")
    
    # Media
    image_url = models.URLField(max_length=500, blank=True, null=True, verbose_name="URL de l'image")
    image = models.ImageField(upload_to='destinations/', blank=True, null=True, verbose_name="Image")
    
    # Pricing - Force DZD currency
    base_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Prix de base (DZD)")
    currency = models.CharField(max_length=3, default='DZD', editable=False, verbose_name="Devise")
    discount_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Pourcentage de réduction"
    )
    
    # Statistics
    rating = models.DecimalField(
        max_digits=3, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        verbose_name="Note"
    )
    total_bookings = models.IntegerField(default=0, verbose_name="Total réservations")
    
    # Status
    status = models.CharField(max_length=50, default='Actif', verbose_name="Statut")
    is_popular = models.BooleanField(default=False, verbose_name="Destination populaire")
    
    # User tracking
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='destinations_created',
        verbose_name="Créé par"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='destinations_updated',
        verbose_name="Mis à jour par"
    )
    
    # Additional Info
    tags = models.TextField(blank=True, verbose_name="Tags (séparés par des virgules)")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Date de mise à jour")
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Destination"
        verbose_name_plural = "Destinations"
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        # Force currency to DZD
        self.currency = 'DZD'
        super().save(*args, **kwargs)
    
    @property
    def final_price(self):
        """Calculate final price after discount in DZD"""
        if self.discount_percentage > 0:
            return float(self.base_price) * (100 - float(self.discount_percentage)) / 100
        return float(self.base_price)
    
    @property
    def display_price(self):
        """Display price with DZD currency"""
        return f"{self.final_price} DZD"
    
    @property
    def tags_list(self):
        """Return tags as list"""
        if self.tags:
            return [tag.strip() for tag in self.tags.split(',')]
        return []


class Offer(models.Model):
    """Special Offers model"""
    
    OFFER_TYPES = [
        ('FLASH', 'Offre Flash'),
        ('SEASONAL', 'Offre Saisonnière'),
        ('WEEKEND', 'Offre Week-end'),
        ('GROUP', 'Offre Groupe'),
        ('LAST_MINUTE', 'Dernière Minute'),
    ]
    
    # Basic Information
    title = models.CharField(max_length=200, verbose_name="Titre de l'offre")
    description = models.TextField(verbose_name="Description")
    
    # Destination relation (optional - can be linked to existing destination)
    destination = models.ForeignKey(
        Destination,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='offers',
        verbose_name="Destination liée"
    )
    
    # Offer details
    offer_type = models.CharField(max_length=50, choices=OFFER_TYPES, default='SEASONAL', verbose_name="Type d'offre")
    location = models.CharField(max_length=200, verbose_name="Lieu/Destination")
    
    # Media
    image_url = models.URLField(max_length=500, blank=True, null=True, verbose_name="URL de l'image")
    image = models.ImageField(upload_to='offers/', blank=True, null=True, verbose_name="Image")
    
    # Pricing - Force DZD currency
    original_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Prix original (DZD)")
    offer_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Prix promotionnel (DZD)")
    currency = models.CharField(max_length=3, default='DZD', editable=False, verbose_name="Devise")
    
    # Duration and dates
    duration_days = models.IntegerField(default=7, verbose_name="Durée (jours)")
    start_date = models.DateField(verbose_name="Date de début")
    end_date = models.DateField(verbose_name="Date de fin")
    
    # What's included
    includes = models.TextField(blank=True, verbose_name="Ce qui est inclus (séparé par des virgules)")
    excludes = models.TextField(blank=True, verbose_name="Ce qui n'est pas inclus (séparé par des virgules)")
    
    # Status
    is_active = models.BooleanField(default=True, verbose_name="Offre active")
    is_featured = models.BooleanField(default=False, verbose_name="Offre vedette")
    
    # Statistics
    total_bookings = models.IntegerField(default=0, verbose_name="Nombre de réservations")
    
    # User tracking
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='offers_created',
        verbose_name="Créé par"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='offers_updated',
        verbose_name="Mis à jour par"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Date de mise à jour")
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Offre spéciale"
        verbose_name_plural = "Offres spéciales"
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        # Force currency to DZD
        self.currency = 'DZD'
        super().save(*args, **kwargs)
    
    @property
    def discount_percentage(self):
        """Calculate discount percentage"""
        if self.original_price > 0:
            return round(((self.original_price - self.offer_price) / self.original_price) * 100, 1)
        return 0
    
    @property
    def includes_list(self):
        """Return includes as list"""
        if self.includes:
            return [item.strip() for item in self.includes.split(',')]
        return []
    
    @property
    def excludes_list(self):
        """Return excludes as list"""
        if self.excludes:
            return [item.strip() for item in self.excludes.split(',')]
        return []


class Review(models.Model):
    """User reviews for destinations"""
    destination = models.ForeignKey(Destination, on_delete=models.CASCADE, related_name='reviews')
    user_name = models.CharField(max_length=100)
    user_email = models.EmailField()
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField()
    is_approved = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Review by {self.user_name} - {self.destination.name}"