from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Login user for any organization.
    Roles cover college + office use-cases.
    """

    class Role(models.TextChoices):
        PLATFORM_ADMIN = "platform_admin", "Platform Admin"
        ORG_ADMIN = "org_admin", "Organization Admin"
        MANAGER = "manager", "Manager / Teacher / HR"
        MEMBER = "member", "Member / Student / Employee"
        RECEPTION = "reception", "Reception / Guard"

    organization = models.ForeignKey(
        "orgs.Organization",
        on_delete=models.CASCADE,
        related_name="users",
        null=True,
        blank=True,
        help_text="Null only for platform_admin users.",
    )
    role = models.CharField(
        max_length=32,
        choices=Role.choices,
        default=Role.MEMBER,
    )

    def __str__(self) -> str:
        org = self.organization.slug if self.organization_id else "platform"
        return f"{self.username} [{self.role} @ {org}]"
