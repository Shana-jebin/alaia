from django.shortcuts import render, redirect, get_object_or_404,HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Q
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from django.http import JsonResponse
from products.models import Category




User = get_user_model()

def is_admin(user):
    return user.is_authenticated and user.is_staff

@never_cache
@csrf_protect
def admin_login(request):

    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect('admin_dashboard')
        return redirect('home')

    if request.method == "POST":
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        user = authenticate(request, username=username, password=password)

        if user is None:
            messages.error(request, "Invalid credentials.")
        elif not user.is_staff:
            messages.error(request, "You don't have admin access.")
        elif not user.is_active:
            messages.error(request, "This account is blocked.")
        else:
            login(request, user)
            return redirect('admin_dashboard')

    return render(request, 'adminpanel/admin-login.html')

@never_cache
@login_required
@user_passes_test(is_admin, login_url='admin_login')
def admin_dashboard(request):
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    blocked_users = User.objects.filter(is_active=False).count()

    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_signups = User.objects.filter(
        date_joined__gte=today_start
    ).count()

    context = {
        'total_users': total_users,
        'active_users': active_users,
        'blocked_users': blocked_users,
        'today_signups': today_signups,
        'username': request.user.get_full_name() or request.user.username,  # for "Welcome back"
    }

    return render(request, 'adminpanel/dashboard.html', context)

@never_cache
@login_required
@user_passes_test(is_admin)
def user_management(request):
    query = request.GET.get('q', '').strip()
    page_number = request.GET.get('page')

    users = User.objects.filter(is_superuser=False).order_by('-date_joined')


    if query:
        users = users.filter(
            Q(email__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(username__icontains=query)
        )

    paginator = Paginator(users, 10)
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'query': query,
    }

    return render(request, 'adminpanel/user_list.html', context)

@never_cache
@login_required
@user_passes_test(is_admin)
def toggle_block_user(request, user_id):
    if request.method == "POST":
        user = get_object_or_404(User, id=user_id)

        if user == request.user:
            messages.error(request, "You cannot block yourself.")
            return redirect('user_management')

        if user.is_active:
            user.is_active = False
            messages.success(request, f"{user.username} has been blocked.")
        else:
            user.is_active = True
            messages.success(request, f"{user.username} has been unblocked.")

        user.save()

    return redirect('user_management')




@login_required
@user_passes_test(is_admin)
def search_users(request):
    query = request.GET.get('q', '').strip()

    users = User.objects.filter(is_superuser=False)

    if query:
        users = users.filter(username__istartswith=query
)

    data = [
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
            "date_joined": user.date_joined.strftime("%b %d, %Y")
        }
        for user in users
    ]

    return JsonResponse({"users": data})


@login_required
@user_passes_test(is_admin)
def admin_category_list(request):

    query = request.GET.get('q', '')

    categories = Category.objects.filter(is_deleted=False)

    if query:
        categories = categories.filter(name__icontains=query)

    categories = categories.order_by('-created_at')

    paginator = Paginator(categories, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'query': query,
    }

    return render(request, 'adminpanel/category-management.html', context)







@never_cache
def admin_logout(request):
    logout(request)
    return redirect('admin_login')


