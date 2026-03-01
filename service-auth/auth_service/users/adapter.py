# users/adapter.py
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialAccount

class MySocialAccountAdapter(DefaultSocialAccountAdapter):
    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        
        # Get data from Google
        google_data = sociallogin.account.extra_data
        
        # Extract first and last name from Google
        # Google typically provides 'given_name' and 'family_name'
        given_name = google_data.get('given_name', '')
        family_name = google_data.get('family_name', '')
        
        # Or sometimes just 'name' field that needs parsing
        full_name = google_data.get('name', '')
        
        # If we have given_name and family_name, use them
        if given_name and family_name:
            user.prenom = given_name
            user.nom = family_name
        # Otherwise try to parse from full name
        elif full_name:
            name_parts = full_name.split(' ', 1)
            user.prenom = name_parts[0]
            user.nom = name_parts[1] if len(name_parts) > 1 else ''
        
        # Save the user
        user.save()
        
        return user