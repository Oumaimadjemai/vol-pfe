# users/adapter.py
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from .models import Voyageur

class MySocialAccountAdapter(DefaultSocialAccountAdapter):
    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        user.role = 'voyageur'
        user.save()
        
        # Create Voyageur profile immediately
        if not hasattr(user, 'voyageur'):
            # Try to extract name from Google data
            nom = ''
            prenom = ''
            
            if sociallogin.account.provider == 'google':
                extra_data = sociallogin.account.extra_data
                if 'name' in extra_data:
                    full_name = extra_data.get('name', '')
                    name_parts = full_name.split(' ', 1)
                    nom = name_parts[0] if name_parts else ''
                    prenom = name_parts[1] if len(name_parts) > 1 else ''
                elif 'given_name' in extra_data and 'family_name' in extra_data:
                    prenom = extra_data.get('given_name', '')
                    nom = extra_data.get('family_name', '')
            
            Voyageur.objects.create(
                user=user,
                nom=nom,
                prenom=prenom,
                telephone='',
                pays='',
                wilaya='',
                commune='',
            )
        
        return user