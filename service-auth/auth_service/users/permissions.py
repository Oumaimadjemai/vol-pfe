from rest_framework.permissions import BasePermission


class IsVoyageur(BasePermission):
    def has_permission(self, request, view):
        return request.user.role == "voyageur"


class IsAdminOrAgent(BasePermission):
    def has_permission(self, request, view):
        return request.user.role in ["admin", "agent"]
