# users/signals.py
from django.dispatch import receiver
from allauth.account.signals import user_signed_up
from allauth.socialaccount.signals import social_account_added
from .models import User, Voyageur

@receiver(user_signed_up)
@receiver(social_account_added)  # Also catch social account added signal
def create_voyageur_profile(request, user, **kwargs):
    """
    When a new user signs up via OAuth or normal registration,
    set their role to 'voyageur' and create a Voyageur profile.
    """
    # Only if role isn't set yet
    if not user.role:
        user.role = 'voyageur'
        user.save()

    # Create a Voyageur profile if it doesn't exist
    if not hasattr(user, 'voyageur'):
        # Try to get name from social account if available
        nom = ''
        prenom = ''
        
        # Check if this came from a social login
        social_accounts = user.socialaccount_set.all()
        if social_accounts.exists():
            social_account = social_accounts.first()
            if social_account.provider == 'google':
                # Extract name from Google data
                extra_data = social_account.extra_data
                if 'name' in extra_data:
                    # Try to split full name
                    full_name = extra_data.get('name', '')
                    name_parts = full_name.split(' ', 1)
                    nom = name_parts[0] if name_parts else ''
                    prenom = name_parts[1] if len(name_parts) > 1 else ''
                elif 'given_name' in extra_data and 'family_name' in extra_data:
                    prenom = extra_data.get('given_name', '')
                    nom = extra_data.get('family_name', '')

        Voyageur.objects.create(
            user=user,
            nom=nom or '',  # Empty string if no name
            prenom=prenom or '',
            telephone='',   # Empty string as default
            pays='',
            wilaya='',
            commune='',
        )