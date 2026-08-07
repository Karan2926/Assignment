from rest_framework import generics
from rest_framework.permissions import AllowAny

from .models import Organization
from .serializers import OrganizationSerializer


class OrganizationListCreateView(generics.ListCreateAPIView):
    """
    Phase 1 helper: list/create organizations.
    Later we will lock create behind platform/org admin auth.
    """

    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    permission_classes = [AllowAny]
