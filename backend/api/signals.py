from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from api.models import Organization, OrganizationBoard, PersonalBoard, UserProfile


@receiver(post_save, sender=User)
def ensure_user_profile_and_board(sender, instance, created, **kwargs):
    UserProfile.objects.get_or_create(user=instance)
    PersonalBoard.objects.get_or_create(user=instance)


@receiver(post_save, sender=Organization)
def ensure_organization_board(sender, instance, created, **kwargs):
    OrganizationBoard.objects.get_or_create(organization=instance)
