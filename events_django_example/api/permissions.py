from django.http import Http404
from rest_framework import permissions


class IsOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if view.action in ['create', 'update', 'partial_update', 'destroy']:
            return obj.user_id == request.user.id
        return True


class RelatedEventObjectPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        parent_event = view.get_parent_object()
        if parent_event.is_private:
            if parent_event.user_id != request.user.id:
                if not parent_event.attendance_set.filter(user_id=request.user.id).exists():
                    raise Http404()
        return True


class RelatedEventOwner(permissions.BasePermission):
    def has_permission(self, request, view):
        parent_event = view.get_parent_object()
        if view.action in ['create', 'update', 'partial_update', 'destroy']:
            return parent_event.user_id == request.user.id
        return True
