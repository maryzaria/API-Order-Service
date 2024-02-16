from rest_framework.permissions import BasePermission


class IsShop(BasePermission):
    message = 'Доступно только для магазинов'

    def has_permission(self, request, view):
        user = request.user
        return user.user_type == "shop"


class IsOwner(BasePermission):
    message = 'Log in required"'

    def has_object_permission(self, request, view, obj):
        return obj.user == request.user