from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from accounts.models import Profile 
import random
from django.core.mail import send_mail
from accounts.models import EmailOTP
from django.conf import settings 
from django.views.decorators.cache import never_cache, cache_control
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from accounts.models import Address
from django.shortcuts import get_object_or_404
from django.contrib import messages




@login_required
def profile_view(request):
    profile, created = Profile.objects.get_or_create(user=request.user)

    is_google_user = request.user.socialaccount_set.exists()
    
    if is_google_user and (not request.user.first_name or not request.user.last_name):
        messages.warning(request, "Please complete your profile information.")


    if request.method == "POST":

        user = request.user
        user.first_name = request.POST.get("first_name", "").strip()
        user.last_name = request.POST.get("last_name", "").strip()

        if not user.first_name or not user.last_name:
            messages.error(request, "First name and Last name cannot be empty.")
            return redirect("profile")

        new_email = request.POST.get("email")
        print("Current email:", user.email)
        print("Submitted email:", new_email)

        if is_google_user:
            if new_email != user.email:
                messages.error(request, "You cannot change email because you signed in with Google.")
                return redirect("profile")
        else:
           
            if new_email != user.email:

                if User.objects.filter(email=new_email).exclude(id=user.id).exists():

                    messages.error(request, "This email is already registered.")
                    return redirect("profile")

                request.session["new_email"] = new_email
                return redirect("verify_email_otp")


        user.save()

        profile.phone = request.POST.get("phone")
        if request.FILES.get("image"):
            profile.image = request.FILES.get("image")

        profile.save()

        return redirect("profile")

    return render(request, "user_profile/profile.html", {
        "is_google_user": is_google_user
    })



@login_required
def verify_email_otp(request):

    if 'new_email' not in request.session:
        print("No new_email in session")
        return redirect('profile')

    new_email = request.session.get('new_email')

    if request.method == "POST":
        entered_otp = request.POST.get('otp')
        print("Entered OTP:", entered_otp)

        otp_record = EmailOTP.objects.filter(
            email=new_email
        ).order_by('-created_at').first()

        if otp_record and otp_record.otp == entered_otp and not otp_record.is_expired():

            request.user.email = new_email
            request.user.save()

            otp_record.delete()
            del request.session['new_email']

            messages.success(request, "Email updated successfully ✔")
            return redirect('profile')

        messages.error(request, "Invalid or expired OTP.")
        return redirect('verify_email_otp')

    # GET request
    EmailOTP.objects.filter(email=new_email).delete()

    otp = str(random.randint(100000, 999999))
    print("Generated OTP:", otp)

    EmailOTP.objects.create(email=new_email, otp=otp)

    send_mail(
        'ALAIA Email Change Verification',
        f'Your OTP is: {otp}',
        settings.EMAIL_HOST_USER,
        [new_email],
    )

    return render(request, 'user_profile/verify-email.html')

@login_required
def resend_otp(request):

    new_email = request.session.get('new_email')

    if not new_email:
        return redirect('profile')

    EmailOTP.objects.filter(email=new_email).delete()

    otp = str(random.randint(100000, 999999))

    print("Resent OTP:", otp)

    EmailOTP.objects.create(
        email=new_email,
        otp=otp
    )

    send_mail(
        'ALAIA Email Change Verification',
        f'Your new OTP is: {otp}',
        settings.EMAIL_HOST_USER,
        [new_email],
    )

    messages.success(request, "New OTP sent successfully ✔")
    return redirect('verify_email_otp')


@login_required
def address_list(request):
    addresses = Address.objects.filter(user=request.user).order_by('-created_at')

    return render(request, "user_profile/address-management.html", {
    "addresses": addresses,
    "active_page": "addresses"
})




def add_address(request):
    if request.method == "POST":
        full_name = request.POST.get("full_name")
        address_line1 = request.POST.get("address_line1")
        address_line2 = request.POST.get("address_line2")
        city = request.POST.get("city")
        state = request.POST.get("state")
        postal_code = request.POST.get("postal_code")
        country = request.POST.get("country")
        phone = request.POST.get("phone")
        is_default = request.POST.get("is_default")

        if not Address.objects.filter(user=request.user).exists():
            is_default = True
      
        if is_default:
            Address.objects.filter(user=request.user).update(is_default=False)

        Address.objects.create(
            user=request.user,
            full_name=full_name,
            address_line1=address_line1,
            address_line2=address_line2,
            city=city,
            state=state,
            postal_code=postal_code,
            country=country,
            phone=phone,
            is_default=True if is_default else False
        )

        messages.success(request, "Address added successfully!")
        return redirect("address_list")


    return render(request, "user_profile/add-address.html")




def edit_address(request, id):
    address = get_object_or_404(Address, id=id, user=request.user)

    if request.method == "POST":
        address.full_name = request.POST.get("full_name")
        address.address_line1 = request.POST.get("address_line1")
        address.address_line2 = request.POST.get("address_line2")
        address.city = request.POST.get("city")
        address.state = request.POST.get("state")
        address.postal_code = request.POST.get("postal_code")
        address.country = request.POST.get("country")
        address.phone = request.POST.get("phone")
        is_default = bool(request.POST.get("is_default"))

        if is_default:
  
            Address.objects.filter(user=request.user, is_default=True).exclude(id=address.id).update(is_default=False)
            address.is_default = True
        else:
   
            if address.is_default and not Address.objects.filter(user=request.user, is_default=True).exclude(id=address.id).exists():
                address.is_default = True
            else:
                address.is_default = False

        address.save()

        messages.success(request, "Address updated successfully!")
        return redirect("address_list")


    return render(request, 'user_profile/add-address.html', {'address': address})


def delete_address(request, id):
    address = get_object_or_404(Address, id=id, user=request.user)

    if request.method == "POST":
        was_default = address.is_default
        address.delete()

        if was_default:
            new_default = Address.objects.filter(user=request.user).first()
            if new_default:
                new_default.is_default = True
                new_default.save()
        messages.success(request, "Address deleted successfully!")
        return redirect('address_list')

    return redirect('address_list')


def set_default_address(request, id):
    address = get_object_or_404(Address, id=id, user=request.user)

    Address.objects.filter(user=request.user).update(is_default=False)
    address.is_default = True
    address.save()

    messages.success(request, "Default address updated successfully!")
    return redirect('address_list')




