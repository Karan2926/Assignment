from django.db import models


class Organization(models.Model):
    """
    One customer account: college, office, factory, coaching, etc.
    All people/attendance data belongs to an organization.
    """

    class OrgType(models.TextChoices):
        EDUCATION = "education", "Education (school/college)"
        CORPORATE = "corporate", "Corporate office"
        INDUSTRIAL = "industrial", "Factory / industrial"
        COACHING = "coaching", "Coaching / training"
        OTHER = "other", "Other"

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=80, unique=True)
    org_type = models.CharField(
        max_length=32,
        choices=OrgType.choices,
        default=OrgType.EDUCATION,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.org_type})"
