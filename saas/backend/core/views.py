from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    """Simple ping so React can verify backend is running."""
    return Response(
        {
            "status": "ok",
            "service": "smart-attendance-saas",
            "phase": 1,
            "message": "Django backend is running",
        }
    )
