from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from .forms import SignupForm, LoginForm

User = get_user_model()

def signup_view(request):
    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser:
            return redirect('admin_panel')
        return redirect('home')

    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Account created successfully!')
            return redirect('home')
    else:
        form = SignupForm()
    
    return render(request, 'fit/signup.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser:
            return redirect('admin_panel')
        return redirect('home')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('email')
            password = form.cleaned_data.get('password')
            user = authenticate(request, email=email, password=password)
            if user is not None:
                if not user.is_active:
                    messages.error(request, 'Your account has been suspended. Please contact administration.')
                    return render(request, 'fit/login.html', {'form': form})
                
                login(request, user)
                messages.success(request, f'Welcome back, {user.name}!')
                if user.is_staff or user.is_superuser:
                    return redirect('admin_panel')
                return redirect('home')
            else:
                messages.error(request, 'Invalid email or password.')
    else:
        form = LoginForm()
    
    return render(request, 'fit/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('login')


@login_required(login_url='login')
def home_view(request):
    return render(request, 'fit/home.html')


@login_required(login_url='login')
@user_passes_test(lambda u: u.is_staff or u.is_superuser, login_url='home')
def admin_panel_view(request):
    users = User.objects.all().order_by('-id')
    total_users = users.count()
    male_users = users.filter(gender='M').count()
    female_users = users.filter(gender='F').count()
    other_users = users.filter(gender='O').count()
    
    ages = [u.age for u in users if u.age is not None]
    avg_age = sum(ages) / len(ages) if ages else 0
    
    context = {
        'users': users,
        'total_users': total_users,
        'male_users': male_users,
        'female_users': female_users,
        'other_users': other_users,
        'avg_age': round(avg_age, 1),
    }
    return render(request, 'fit/admin_panel.html', context)


from django.shortcuts import get_object_or_404

@login_required(login_url='login')
@user_passes_test(lambda u: u.is_staff or u.is_superuser, login_url='home')
def toggle_user_status_view(request, user_id):
    if request.method == 'POST':
        user_to_toggle = get_object_or_404(User, id=user_id)
        if user_to_toggle == request.user:
            messages.error(request, "You cannot block your own administrative account!")
        else:
            user_to_toggle.is_active = not user_to_toggle.is_active
            user_to_toggle.save()
            status = "blocked" if not user_to_toggle.is_active else "unblocked"
            messages.success(request, f"User {user_to_toggle.name} has been {status} successfully.")
    return redirect('admin_panel')
