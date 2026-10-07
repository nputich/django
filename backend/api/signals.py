from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from api.control_numbers import ensure_org_control_number, ensure_user_control_number
from api.models import Organization, OrganizationBoard, PersonalBoard, UserProfile


@receiver(post_save, sender=User)
def ensure_user_profile_and_board(sender, instance, created, **kwargs):
    profile, _ = UserProfile.objects.get_or_create(user=instance)
    ensure_user_control_number(profile)
    PersonalBoard.objects.get_or_create(user=instance)


@receiver(post_save, sender=Organization)
def ensure_organization_board(sender, instance, created, **kwargs):
    OrganizationBoard.objects.get_or_create(organization=instance)
    ensure_org_control_number(instance)
