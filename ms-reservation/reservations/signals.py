from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Reservation, Payment
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Reservation)
def reservation_post_save(sender, instance, created, **kwargs):
    """Handle reservation post-save actions"""
    if created:
        logger.info(f"New reservation created: {instance.reservation_number}")
    elif instance.status == 'CONFIRMED':
        logger.info(f"Reservation confirmed: {instance.reservation_number}")
    elif instance.status == 'CANCELLED':
        logger.info(f"Reservation cancelled: {instance.reservation_number}")


@receiver(post_save, sender=Payment)
def payment_post_save(sender, instance, created, **kwargs):
    """Handle payment post-save actions"""
    if created:
        logger.info(f"New payment created for reservation: {instance.reservation.reservation_number}")
    elif instance.status == 'COMPLETED':
        logger.info(f"Payment completed for reservation: {instance.reservation.reservation_number}")