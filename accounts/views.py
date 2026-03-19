from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.contrib.auth.models import User
import random
from .models import EmailOTP, Profile, ReferralCode, ReferralUsage
from django.core.mail import send_mail
from django.views.decorators.cache import never_cache, cache_control
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.utils import timezone
from datetime import timedelta
from django.contrib import messages
from django.conf import settings


# ── HELPERS ───────────────────────────────────────────────────────

def generate_otp():
    return str(random.randint(100000, 999999))


# ── LOGIN ─────────────────────────────────────────────────────────

@never_cache
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@csrf_protect
def login_view(request):
    errors = {}
    old = {}

    if request.method == "POST":
        email    = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        old      = {"email": email}

        if not email:
            errors["email"] = "Email is required."
        if not password:
            errors["password"] = "Password is required."

        if not errors:
            user = authenticate(request, username=email, password=password)
            if user is None:
                errors["password"] = "Invalid email or password."
            else:
                login(request, user)
                return redirect("home")

        return render(request, "accounts/login.html", {"errors": errors, "old": old})

    return render(request, "accounts/login.html")


# ── SIGNUP ────────────────────────────────────────────────────────

@never_cache
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@csrf_protect
def signup_view(request):
    errors = {}
    old    = {}

    if request.method == "POST":
        first_name       = request.POST.get("first_name", "").strip()
        last_name        = request.POST.get("last_name", "").strip()
        email            = request.POST.get("email", "").strip()
        password         = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")
        phone            = request.POST.get("phone", "").strip()
        referral_code    = request.POST.get("referral_code", "").strip().upper()

        old = {
            "first_name":    first_name,
            "last_name":     last_name,
            "email":         email,
            "phone":         phone,
            "referral_code": referral_code,
        }

        if not first_name:
            errors["first_name"] = "First name is required."
        if not last_name:
            errors["last_name"] = "Last name is required."
        if not email:
            errors["email"] = "Email is required."
        if not phone:
            errors["phone"] = "Mobile number is required."
        elif not phone.isdigit():
            errors["phone"] = "Mobile number must contain only numbers."
        elif len(phone) != 10:
            errors["phone"] = "Mobile number must be exactly 10 digits."
        if User.objects.filter(username=email).exists():
            errors["email"] = "Email already registered."
        if not password:
            errors["password"] = "Password is required."
        elif len(password) < 8:
            errors["password"] = "Password must be at least 8 characters."
        if not confirm_password:
            errors["confirm_password"] = "Please confirm your password."
        elif password != confirm_password:
            errors["confirm_password"] = "Passwords do not match."

        # Validate referral code if provided (don't block signup if invalid)
        referral_error = ''
        if referral_code:
            if not ReferralCode.objects.filter(code=referral_code).exists():
                referral_error = "Invalid referral code."
                errors["referral_code"] = referral_error

        if errors:
            return render(request, "accounts/signup.html", {"errors": errors, "old": old})

        phone = "+91" + phone
        otp   = generate_otp()
        print(f"Generated OTP for {email}: {otp}")

        EmailOTP.objects.filter(email=email).delete()
        EmailOTP.objects.create(email=email, otp=otp)

        send_mail(
            'ALAIA OTP Verification',
            f'Your OTP is: {otp}',
            settings.EMAIL_HOST_USER,
            [email],
        )

        request.session['signup_data'] = {
            'first_name':    first_name,
            'last_name':     last_name,
            'email':         email,
            'password':      password,
            'phone':         phone,
            'referral_code': referral_code,
        }
        messages.success(request, "A verification code has been sent to your email ✔")
        return redirect('accounts:verify_otp')

    return render(request, "accounts/signup.html", {"errors": {}, "old": {}})


# ── VERIFY OTP ────────────────────────────────────────────────────

@never_cache
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@csrf_protect
def verify_otp(request):
    if 'signup_data' not in request.session:
        return redirect('signup')

    if request.method == "POST":
        entered_otp = request.POST.get('otp')
        signup_data = request.session.get('signup_data')

        if not entered_otp or len(entered_otp) != 6:
            messages.error(request, "Please enter valid 6 digit OTP")
            return redirect('accounts:verify_otp')

        otp_record = EmailOTP.objects.filter(
            email=signup_data['email']
        ).order_by('-created_at').first()

        if not otp_record:
            messages.error(request, "No OTP found. Please resend.")
            return redirect('accounts:verify_otp')
        if otp_record.is_expired():
            messages.error(request, "OTP expired. Please resend.")
            return redirect('accounts:verify_otp')
        if otp_record.otp != entered_otp:
            messages.error(request, "Invalid OTP")
            return redirect('accounts:verify_otp')

        # ── Create user ──
        user = User.objects.create_user(
            username=signup_data['email'],
            email=signup_data['email'],
            password=signup_data['password'],
            first_name=signup_data.get('first_name', ''),
            last_name=signup_data.get('last_name', ''),
        )

        profile, _ = Profile.objects.get_or_create(user=user)
        profile.phone = signup_data.get('phone')
        profile.save()

        ReferralCode.objects.get_or_create(user=user)

 
        referral_code = signup_data.get('referral_code', '').strip().upper()
        if referral_code:
            try:
                ref_obj  = ReferralCode.objects.get(code=referral_code)
                referrer = ref_obj.user

             
                if referrer != user:
                   
                    ReferralUsage.objects.create(referrer=referrer, referee=user)

                    ref_obj.used_count += 1
                    ref_obj.save(update_fields=['used_count'])

                  
                    from orders.models import Wallet
                    referrer_wallet, _ = Wallet.objects.get_or_create(user=referrer)
                    referee_wallet,  _ = Wallet.objects.get_or_create(user=user)

                    referrer_wallet.credit(
                        ReferralUsage.REFERRER_REWARD,
                        description=f"Referral reward — {user.email} signed up with your code",
                    )
                    referee_wallet.credit(
                        ReferralUsage.REFEREE_REWARD,
                        description=f"Welcome bonus — you signed up with referral code {referral_code}",
                    )

                    print(f"Referral processed: {referrer.email} → {user.email}")

            except ReferralCode.DoesNotExist:
                pass 
        otp_record.delete()
        request.session.flush()

        messages.success(request, "Account created successfully ✔ Please login.")
        return redirect('accounts:login')

    return render(request, 'accounts/verify_otp.html')




def resend_otp(request):
    data = request.session.get('signup_data')
    if not data:
        return redirect('accounts:signup')

    EmailOTP.objects.filter(email=data['email']).delete()
    otp = generate_otp()
    EmailOTP.objects.create(email=data['email'], otp=otp)

    send_mail(
        'ALAIA OTP Verification',
        f'Your new OTP is: {otp}',
        settings.EMAIL_HOST_USER,
        [data['email']],
    )
    messages.success(request, "New OTP sent successfully ✔")
    return redirect('accounts:verify_otp')


# ── FORGOT PASSWORD ───────────────────────────────────────────────

@never_cache
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@csrf_protect
def forgot_password(request):
    request.session.pop('reset_email', None)
    request.session.pop('reset_verified', None)

    if request.method == "POST":
        email = request.POST.get('email', '').strip()
        user  = User.objects.filter(username=email).first()

        if not user:
            messages.error(request, "No account found with this email.")
            return render(request, 'accounts/forgot-password.html', {'email': email})

        otp_record = EmailOTP.objects.filter(email=email).order_by('-created_at').first()
        if otp_record and not otp_record.is_expired():
            messages.error(request, "OTP already sent. Please wait before requesting again.")
            return redirect('accounts:forgot-otp')

        otp = generate_otp()
        print(f"Generated Forgot OTP for {email}: {otp}")
        EmailOTP.objects.filter(email=email).delete()
        EmailOTP.objects.create(email=email, otp=otp)

        send_mail(
            'Password Reset OTP - ALAIA',
            f'Your OTP is: {otp}',
            settings.EMAIL_HOST_USER,
            [email],
        )
        request.session['reset_email'] = email
        messages.success(request, "A verification code has been sent to your email.")
        return redirect('accounts:forgot-otp')

    return render(request, 'accounts/forgot-password.html')


# ── FORGOT OTP ────────────────────────────────────────────────────

@never_cache
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@csrf_protect
def forgot_otp(request):
    email = request.session.get('reset_email')
    if not email:
        return redirect('forgot-password')

    if request.method == "POST":
        entered_otp = request.POST.get('otp')

        if not entered_otp or len(entered_otp) != 6:
            messages.error(request, "Enter valid 6 digit OTP.")
            return redirect('accounts:forgot-otp')

        otp_record = EmailOTP.objects.filter(email=email).order_by('-created_at').first()
        if not otp_record:
            messages.error(request, "OTP not found.")
            return redirect('accounts:forgot-otp')
        if otp_record.is_expired():
            messages.error(request, "OTP expired.")
            return redirect('accounts:forgot-otp')
        if otp_record.otp != entered_otp:
            messages.error(request, "The verification code you entered is incorrect.")
            return redirect('accounts:forgot-otp')

        request.session['reset_verified'] = True
        return redirect('accounts:reset-password')

    return render(request, 'accounts/forgot-otp.html')


def resend_forgot_otp(request):
    email = request.session.get('reset_email')
    if not email:
        return redirect('forgot-password')

    otp = generate_otp()
    print(f"New Forgot OTP for {email}: {otp}")
    EmailOTP.objects.filter(email=email).delete()
    EmailOTP.objects.create(email=email, otp=otp)

    send_mail(
        'New Password Reset OTP - ALAIA',
        f'Your new OTP is: {otp}',
        settings.EMAIL_HOST_USER,
        [email],
    )
    messages.success(request, "New OTP sent successfully.")
    return redirect('accounts:forgot-otp')


# ── RESET PASSWORD ────────────────────────────────────────────────

@never_cache
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@csrf_protect
def reset_password(request):
    email    = request.session.get('reset_email')
    verified = request.session.get('reset_verified')

    if not email or not verified:
        return redirect('forgot-password')

    if request.method == "POST":
        new_password     = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if new_password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect('accounts:reset-password')

        user = User.objects.filter(username=email).first()
        if not user:
            messages.error(request, "User not found.")
            return redirect('forgot-password')

        user.set_password(new_password)
        user.save()
        request.session.flush()
        messages.success(request, "Password reset successful ✔")
        return redirect('accounts:login')

    return render(request, 'accounts/reset-password.html')


# ── LOGOUT ────────────────────────────────────────────────────────

def logout_view(request):
    logout(request)
    return redirect('/')


# ── REFERRAL PAGE ─────────────────────────────────────────────────

@login_required
def referral_page(request):
    """User's referral dashboard — shows their code and referral history."""
    ref_obj, _ = ReferralCode.objects.get_or_create(user=request.user)
    referrals   = ReferralUsage.objects.filter(
        referrer=request.user
    ).select_related('referee').order_by('-created_at')

    from orders.models import Wallet
    wallet, _ = Wallet.objects.get_or_create(user=request.user)

    return render(request, 'user_profile/referral.html', {
        'ref_obj':   ref_obj,
        'referrals': referrals,
        'wallet':    wallet,
        'referrer_reward': ReferralUsage.REFERRER_REWARD,
        'referee_reward':  ReferralUsage.REFEREE_REWARD,
    })