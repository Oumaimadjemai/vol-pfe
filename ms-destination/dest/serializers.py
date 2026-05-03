from rest_framework import serializers
from .models import Destination, Offer, Review


class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ['id', 'user_name', 'user_email', 'rating', 'comment', 'is_approved', 'created_at']
        read_only_fields = ['created_at', 'is_approved']


class DestinationListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list view"""
    final_price = serializers.ReadOnlyField()
    display_price = serializers.ReadOnlyField()
    tags_list = serializers.ReadOnlyField()
    created_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Destination
        fields = [
            'id', 'name', 'country', 'city', 'continent', 
            'description', 'image_url', 'final_price', 'display_price', 
            'currency', 'rating', 'total_bookings', 'status', 
            'is_popular', 'discount_percentage', 'tags_list',
            'created_at', 'created_by_name'
        ]
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.email
        return None


class DestinationDetailSerializer(serializers.ModelSerializer):
    """Full serializer for detail view"""
    final_price = serializers.ReadOnlyField()
    display_price = serializers.ReadOnlyField()
    tags_list = serializers.ReadOnlyField()
    reviews = ReviewSerializer(many=True, read_only=True)
    created_by_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Destination
        fields = '__all__'
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.email
        return None
    
    def get_updated_by_name(self, obj):
        if obj.updated_by:
            return obj.updated_by.email
        return None


class DestinationCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for create/update operations"""
    class Meta:
        model = Destination
        fields = '__all__'
        read_only_fields = ['currency', 'created_by', 'updated_by']
    
    def validate_name(self, value):
        if len(value) < 3:
            raise serializers.ValidationError("Le nom doit contenir au moins 3 caractères")
        return value
    
    def validate_base_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Le prix doit être supérieur à 0")
        return value


class OfferListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for offer list view"""
    display_original_price = serializers.SerializerMethodField()
    display_offer_price = serializers.SerializerMethodField()
    discount_percentage = serializers.ReadOnlyField()
    created_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Offer
        fields = [
            'id', 'title', 'location', 'description', 'image_url',
            'original_price', 'offer_price', 'display_original_price', 'display_offer_price',
            'discount_percentage', 'duration_days', 'start_date', 'end_date',
            'is_active', 'is_featured', 'total_bookings', 'offer_type',
            'created_at', 'created_by_name','includes','excludes'
        ]
    
    def get_display_original_price(self, obj):
        return f"{obj.original_price} DZD"
    
    def get_display_offer_price(self, obj):
        return f"{obj.offer_price} DZD"
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.email
        return None


class OfferDetailSerializer(serializers.ModelSerializer):
    """Full serializer for offer detail view"""
    display_original_price = serializers.SerializerMethodField()
    display_offer_price = serializers.SerializerMethodField()
    discount_percentage = serializers.ReadOnlyField()
    includes_list = serializers.ReadOnlyField()
    excludes_list = serializers.ReadOnlyField()
    created_by_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()
    destination_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Offer
        fields = '__all__'
    
    def get_display_original_price(self, obj):
        return f"{obj.original_price} DZD"
    
    def get_display_offer_price(self, obj):
        return f"{obj.offer_price} DZD"
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.email
        return None
    
    def get_updated_by_name(self, obj):
        if obj.updated_by:
            return obj.updated_by.email
        return None
    
    def get_destination_name(self, obj):
        if obj.destination:
            return obj.destination.name
        return None


class OfferCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for create/update operations"""
    class Meta:
        model = Offer
        fields = '__all__'
        read_only_fields = ['currency', 'created_by', 'updated_by']
    
    def validate(self, data):
        if data['start_date'] > data['end_date']:
            raise serializers.ValidationError("La date de fin doit être postérieure à la date de début")
        if data['offer_price'] > data['original_price']:
            raise serializers.ValidationError("Le prix promotionnel doit être inférieur au prix original")
        return data