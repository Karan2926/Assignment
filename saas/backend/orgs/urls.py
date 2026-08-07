from django.urls import path

from .views import OrganizationListCreateView

urlpatterns = [
    path("organizations/", OrganizationListCreateView.as_view(), name="organization-list"),
]
