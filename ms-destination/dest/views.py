from rest_framework import generics, status, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Avg, Sum, Count, Q
from .models import Destination, Offer, Review
from .serializers import (
    DestinationListSerializer, DestinationDetailSerializer, 
    DestinationCreateUpdateSerializer, ReviewSerializer,
    OfferListSerializer, OfferDetailSerializer, OfferCreateUpdateSerializer
)

# Custom Pagination
class DestinationPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


# ============ DESTINATION VIEWS ============

class DestinationListView(generics.ListCreateAPIView):
    """
    GET: List all destinations (with pagination, filtering, search)
    POST: Create a new destination (Admin only)
    """
    queryset = Destination.objects.all()
    serializer_class = DestinationListSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['continent', 'status', 'is_popular', 'country']
    search_fields = ['name', 'city', 'country', 'description']
    ordering_fields = ['rating', 'total_bookings', 'base_price', 'created_at']
    ordering = ['-created_at']
    pagination_class = DestinationPagination
    
    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdminUser()]
        return super().get_permissions()
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return DestinationCreateUpdateSerializer
        return DestinationListSerializer
    
    def perform_create(self, serializer):
        # Only save with created_by if user is authenticated and is a valid User instance
        user = self.request.user
        if user and user.is_authenticated and hasattr(user, 'id'):
            try:
                # Only save if user exists in the database
                if user.id:
                    serializer.save(created_by=user)
                else:
                    serializer.save()
            except Exception as e:
                print(f"Error saving with user: {e}")
                serializer.save()
        else:
            serializer.save()


class DestinationDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET: Retrieve a single destination by ID
    PUT: Update entire destination (Admin only)
    PATCH: Partially update destination (Admin only)
    DELETE: Delete a destination (Admin only)
    """
    queryset = Destination.objects.all()
    serializer_class = DestinationDetailSerializer
    permission_classes = [AllowAny]
    
    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            return [IsAdminUser()]
        return super().get_permissions()
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return DestinationCreateUpdateSerializer
        return DestinationDetailSerializer
    
    def perform_update(self, serializer):
        # Only save with updated_by if user is authenticated
        user = self.request.user
        if user and user.is_authenticated:
            serializer.save(updated_by=user)
        else:
            serializer.save()


class DestinationPopularView(generics.ListAPIView):
    """GET: Get popular destinations"""
    serializer_class = DestinationListSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        return Destination.objects.filter(is_popular=True, status='Actif')[:6]


# ============ OFFER VIEWS ============

class OfferListView(generics.ListCreateAPIView):
    """
    GET: List all offers
    POST: Create a new offer (Admin only)
    """
    queryset = Offer.objects.all()
    serializer_class = OfferListSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['offer_type', 'is_active', 'is_featured']
    search_fields = ['title', 'location', 'description']
    ordering_fields = ['offer_price', 'start_date', 'end_date', 'created_at']
    ordering = ['-created_at']
    pagination_class = DestinationPagination
    
    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdminUser()]
        return super().get_permissions()
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return OfferCreateUpdateSerializer
        return OfferListSerializer
    
    def perform_create(self, serializer):
        # Only save with created_by if user is authenticated
        user = self.request.user
        if user and user.is_authenticated:
            serializer.save(created_by=user)
        else:
            serializer.save()


class OfferDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET: Retrieve a single offer by ID
    PUT: Update entire offer (Admin only)
    PATCH: Partially update offer (Admin only)
    DELETE: Delete an offer (Admin only)
    """
    queryset = Offer.objects.all()
    serializer_class = OfferDetailSerializer
    permission_classes = [AllowAny]
    
    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            return [IsAdminUser()]
        return super().get_permissions()
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return OfferCreateUpdateSerializer
        return OfferDetailSerializer
    
    def perform_update(self, serializer):
        # Only save with updated_by if user is authenticated
        user = self.request.user
        if user and user.is_authenticated:
            serializer.save(updated_by=user)
        else:
            serializer.save()


class OfferActiveView(generics.ListAPIView):
    """GET: Get active offers - PUBLIC ENDPOINT"""
    serializer_class = OfferListSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        from django.utils import timezone
        return Offer.objects.filter(is_active=True, end_date__gte=timezone.now().date())[:6]


class OfferFeaturedView(generics.ListAPIView):
    """GET: Get featured offers"""
    serializer_class = OfferListSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        return Offer.objects.filter(is_featured=True, is_active=True)[:6]


class OfferStatsView(generics.GenericAPIView):
    """GET: Get statistics about offers"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        from django.utils import timezone
        today = timezone.now().date()
        
        stats = {
            'total_offers': Offer.objects.count(),
            'active_offers': Offer.objects.filter(is_active=True, end_date__gte=today).count(),
            'featured_offers': Offer.objects.filter(is_featured=True, is_active=True).count(),
            'total_bookings': Offer.objects.aggregate(total=Sum('total_bookings'))['total'] or 0,
            'by_type': list(Offer.objects.values('offer_type').annotate(
                count=Count('id'),
                total_bookings=Sum('total_bookings')
            )),
        }
        return Response(stats)


class OfferIncrementBookingsView(generics.GenericAPIView):
    """POST: Increment booking count for an offer"""
    permission_classes = [IsAuthenticated]
    queryset = Offer.objects.all()
    
    def post(self, request, pk=None):
        offer = self.get_object()
        offer.total_bookings += 1
        offer.save()
        return Response({
            'success': True,
            'total_bookings': offer.total_bookings,
            'message': f'Booking count incremented for {offer.title}'
        })


# ============ REVIEW VIEWS ============

class ReviewCreateView(generics.CreateAPIView):
    """POST: Add a review for a destination"""
    serializer_class = ReviewSerializer
    permission_classes = [AllowAny]
    
    def perform_create(self, serializer):
        destination_id = self.kwargs.get('destination_id')
        destination = Destination.objects.get(id=destination_id)
        review = serializer.save(destination=destination)
        
        # Update destination rating
        avg_rating = destination.reviews.filter(is_approved=True).aggregate(Avg('rating'))['rating__avg']
        if avg_rating:
            destination.rating = avg_rating
            destination.save()


class ReviewListView(generics.ListAPIView):
    """GET: List all reviews for a destination"""
    serializer_class = ReviewSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        destination_id = self.kwargs.get('destination_id')
        return Review.objects.filter(destination_id=destination_id, is_approved=True)


class ReviewDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET: Retrieve a review
    PUT/PATCH: Update a review (Admin only)
    DELETE: Delete a review (Admin only)
    """
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    
    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            return [IsAdminUser()]
        return [AllowAny()]


# ============ FUNCTION-BASED VIEWS ============

@api_view(['GET'])
@permission_classes([AllowAny])
def get_destinations_by_country(request, country):
    """GET: Get destinations by country"""
    destinations = Destination.objects.filter(country__iexact=country, status='Actif')
    serializer = DestinationListSerializer(destinations, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def search_destinations(request):
    """GET: Search destinations by query parameter"""
    query = request.query_params.get('q', '')
    if query:
        destinations = Destination.objects.filter(
            Q(name__icontains=query) |
            Q(city__icontains=query) |
            Q(country__icontains=query) |
            Q(description__icontains=query),
            status='Actif'
        )
    else:
        destinations = Destination.objects.none()
    
    serializer = DestinationListSerializer(destinations, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def search_offers(request):
    """GET: Search offers by query parameter"""
    query = request.query_params.get('q', '')
    if query:
        offers = Offer.objects.filter(
            Q(title__icontains=query) |
            Q(location__icontains=query) |
            Q(description__icontains=query),
            is_active=True
        )
    else:
        offers = Offer.objects.none()
    
    serializer = OfferListSerializer(offers, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def bulk_delete_destinations(request):
    """POST: Delete multiple destinations at once"""
    ids = request.data.get('ids', [])
    if not ids:
        return Response({'error': 'No IDs provided'}, status=status.HTTP_400_BAD_REQUEST)
    
    deleted_count = Destination.objects.filter(id__in=ids).delete()[0]
    return Response({
        'success': True,
        'deleted_count': deleted_count,
        'message': f'{deleted_count} destinations deleted successfully'
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
def bulk_delete_offers(request):
    """POST: Delete multiple offers at once"""
    ids = request.data.get('ids', [])
    if not ids:
        return Response({'error': 'No IDs provided'}, status=status.HTTP_400_BAD_REQUEST)
    
    deleted_count = Offer.objects.filter(id__in=ids).delete()[0]
    return Response({
        'success': True,
        'deleted_count': deleted_count,
        'message': f'{deleted_count} offers deleted successfully'
    })