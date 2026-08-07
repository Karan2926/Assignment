#!/usr/bin/env python3
"""Create a demo organization + admin user for local testing."""

import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from accounts.models import User  # noqa: E402
from orgs.models import Organization  # noqa: E402


def main() -> None:
    org, _ = Organization.objects.get_or_create(
        slug="demo-office",
        defaults={
            "name": "Demo Office",
            "org_type": Organization.OrgType.CORPORATE,
        },
    )
    user, created = User.objects.get_or_create(
        username="admin",
        defaults={
            "email": "admin@example.com",
            "role": User.Role.ORG_ADMIN,
            "organization": org,
            "is_staff": True,
            "is_superuser": True,
        },
    )
    if created:
        user.set_password("admin123")
        user.save()
        print("Created org=Demo Office, user=admin / admin123")
    else:
        user.organization = org
        user.role = User.Role.ORG_ADMIN
        user.set_password("admin123")
        user.save()
        print("Updated existing admin user (password reset to admin123)")


if __name__ == "__main__":
    main()
