from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver



class EmailOTP(models.Model):
    email = models.EmailField()
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    attempts = models.IntegerField(default=0)


    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(seconds=60)
    




class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=15, blank=True, null=True)
    image = models.ImageField(upload_to='profile_images/', blank=True, null=True)

    def __str__(self):
        return self.user.username







class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="addresses")
    full_name = models.CharField(max_length=150)
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} - {self.city}"
    

import random
import string
 
def generate_referral_code():
    """Generate a unique 8-char referral code like ALAIA-X7K2"""
    chars = string.ascii_uppercase + string.digits
    return 'ALAIA-' + ''.join(random.choices(chars, k=4))
 
 
class ReferralCode(models.Model):
    """One referral code per user, auto-created on signup."""
    user       = models.OneToOneField(User, on_delete=models.CASCADE, related_name='referral_code')
    code       = models.CharField(max_length=20, unique=True)
    used_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
 
    def __str__(self):
        return f"{self.code} → {self.user.email}"
 
    def save(self, *args, **kwargs):
        if not self.code:
            code = generate_referral_code()
            while ReferralCode.objects.filter(code=code).exists():
                code = generate_referral_code()
            self.code = code
        super().save(*args, **kwargs)
 
 
class ReferralUsage(models.Model):
    """Records who referred whom."""
    referrer   = models.ForeignKey(User, on_delete=models.CASCADE, related_name='referrals_made')
    referee    = models.ForeignKey(User, on_delete=models.CASCADE, related_name='referred_by')
    created_at = models.DateTimeField(auto_now_add=True)
 
    
    REFERRER_REWARD = 100  
    REFEREE_REWARD  = 50  
 
    class Meta:
        unique_together = ('referrer', 'referee')
 
    def __str__(self):
        return f"{self.referrer.email} referred {self.referee.email}"

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)
        ReferralCode.objects.get_or_create(user=instance) 