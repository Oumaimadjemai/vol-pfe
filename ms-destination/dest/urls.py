from django.urls import path
from . import views

urlpatterns = [
    # Destination CRUD endpoints
    path('destinations/', views.DestinationListView.as_view(), name='destination-list'),
    path('destinations/<int:pk>/', views.DestinationDetailView.as_view(), name='destination-detail'),
    
    # Destination custom endpoints
    path('destinations/popular/', views.DestinationPopularView.as_view(), name='destination-popular'),
    
    # Offer CRUD endpoints
    path('offers/', views.OfferListView.as_view(), name='offer-list'),
    path('offers/<int:pk>/', views.OfferDetailView.as_view(), name='offer-detail'),
    
    # Offer custom endpoints
    path('offers/active/', views.OfferActiveView.as_view(), name='offer-active'),
    path('offers/featured/', views.OfferFeaturedView.as_view(), name='offer-featured'),
    path('offers/stats/', views.OfferStatsView.as_view(), name='offer-stats'),
    path('offers/<int:pk>/increment-bookings/', views.OfferIncrementBookingsView.as_view(), name='offer-increment-bookings'),
    
    # Search endpoints
    path('destinations/search/', views.search_destinations, name='search-destinations'),
    path('destinations/by-country/<str:country>/', views.get_destinations_by_country, name='destinations-by-country'),
    path('offers/search/', views.search_offers, name='search-offers'),
    
    # Bulk operations (admin only)
    path('destinations/bulk-delete/', views.bulk_delete_destinations, name='bulk-delete'),
    path('offers/bulk-delete/', views.bulk_delete_offers, name='bulk-delete-offers'),
    
    # Review endpoints
    path('destinations/<int:destination_id>/reviews/', views.ReviewListView.as_view(), name='review-list'),
    path('destinations/<int:destination_id>/add-review/', views.ReviewCreateView.as_view(), name='add-review'),
    path('reviews/<int:pk>/', views.ReviewDetailView.as_view(), name='review-detail'),
]