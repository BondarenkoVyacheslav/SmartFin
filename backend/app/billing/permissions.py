from rest_framework.permissions import BasePermission

from .services import has_feature


class HasFeature(BasePermission):
    feature_code = None

    def has_permission(self, request, view):
        code = self.feature_code or getattr(view, 'required_feature', None)
        if not code:
            return True
        return has_feature(request.user, code)
