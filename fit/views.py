from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from .forms import SignupForm, LoginForm
from django.utils import timezone
from dateutil.relativedelta import relativedelta

User = get_user_model()
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from django.utils import timezone


# =========================================================
# SIGNUP
# =========================================================

def signup_view(request):

    # If user is already logged in
    if request.user.is_authenticated:

        # Admin user
        if request.user.is_staff or request.user.is_superuser:
            return redirect('admin_panel')

        # Normal logged-in user
        if request.user.is_paid:
            return redirect('home')

        # Normal user who has not paid
        return redirect('first_time')


    # Signup form submitted
    if request.method == 'POST':

        form = SignupForm(request.POST)

        if form.is_valid():

            # Create the user
            user = form.save()

            messages.success(
                request,
                'Account created successfully! Please login.'
            )

            # IMPORTANT:
            # Do NOT login the user here.
            # Send the new user to the login page.
            return redirect('login')

    else:

        form = SignupForm()


    return render(
        request,
        'fit/signup.html',
        {'form': form}
    )


# =========================================================
# LOGIN
# =========================================================

def login_view(request):

    # If user is already logged in
    if request.user.is_authenticated:

        # Admin user
        if request.user.is_staff or request.user.is_superuser:
            return redirect('admin_panel')

        # Paid normal user
        if request.user.is_paid:
            return redirect('home')

        # Unpaid normal user
        return redirect('first_time')


    # Login form submitted
    if request.method == 'POST':

        form = LoginForm(request.POST)

        if form.is_valid():

            email = form.cleaned_data.get('email')

            password = form.cleaned_data.get('password')


            # Authenticate user
            user = authenticate(
                request,
                email=email,
                password=password
            )


            # User found
            if user is not None:


                # Check whether account is active
                if not user.is_active:

                    messages.error(
                        request,
                        'Your account has been suspended. '
                        'Please contact administration.'
                    )

                    return render(
                        request,
                        'fit/login.html',
                        {'form': form}
                    )


                # Create login session
                login(request, user)


                messages.success(
                    request,
                    f'Welcome back, {user.name}!'
                )


                # =========================================
                # ADMIN USER
                # =========================================

                if user.is_staff or user.is_superuser:

                    return redirect('admin_panel')


                # =========================================
                # NORMAL USER - NOT PAID
                # =========================================

                if not user.is_paid:

                    return redirect('first_time')


                # =========================================
                # NORMAL USER - PAID
                # =========================================

                return redirect('home')


            # Invalid login
            else:

                messages.error(
                    request,
                    'Invalid email or password.'
                )

    else:

        form = LoginForm()


    return render(
        request,
        'fit/login.html',
        {'form': form}
    )


# =========================================================
# LOGOUT
# =========================================================

def logout_view(request):

    logout(request)

    messages.success(
        request,
        'You have been logged out.'
    )

    return redirect('login')


# =========================================================
# HOME
# =========================================================

@login_required(login_url='login')
def home_view(request):

    # -----------------------------------------------------
    # User has not paid
    # -----------------------------------------------------

    if not request.user.is_paid:

        return redirect('first_time')


    # -----------------------------------------------------
    # Paid user must have subscription end date
    # -----------------------------------------------------

    if request.user.subscription_end is None:

        request.user.is_paid = False

        request.user.save(
            update_fields=['is_paid']
        )

        return redirect('first_time')


    # -----------------------------------------------------
    # Subscription expired
    # -----------------------------------------------------

    if request.user.subscription_end <= timezone.now():

        request.user.is_paid = False

        request.user.save(
            update_fields=['is_paid']
        )

        messages.warning(
            request,
            'Your Premium subscription has expired. '
            'Please renew to continue.'
        )

        return redirect('first_time')


    # -----------------------------------------------------
    # User is paid and subscription is active
    # -----------------------------------------------------

    return render(
        request,
        'fit/home.html'
    )


# =========================================================
# FIRST-TIME / PREMIUM PAGE
# =========================================================

@login_required(login_url='login')
def first_time(request):

    # Admin does not need Premium page
    if request.user.is_staff or request.user.is_superuser:
        return redirect('admin_panel')

    # Check whether user already has an active subscription
    if request.user.is_paid:

        if (
            request.user.subscription_end
            and request.user.subscription_end > timezone.now()
        ):
            return redirect('home')

        # Subscription expired
        request.user.is_paid = False
        request.user.subscription_end = None

        request.user.save(
            update_fields=[
                'is_paid',
                'subscription_end'
            ]
        )

    # Check whether payment was started
    payment_started = request.session.get(
        'payment_started',
        False
    )

    return render(
        request,
        'fit/first_time.html',
        {
            'payment_started': payment_started
        }
    )


@login_required(login_url='login')
def start_payment(request):

    # Remember that this user started payment
    request.session['payment_started'] = True

    # Your UPI payment link
    upi_url = (
        'upi://pay?'
        'pa=muhammedrazi01091@oksbi'
        '&pn=FitFusion'
        '&am=19'
        '&cu=INR'
    )

    return redirect(upi_url)


@login_required(login_url='login')
def confirm_payment(request):

    if request.method == 'POST':

        user = request.user

        # Activate Premium
        user.is_paid = True

        # Give 1 month Premium
        user.subscription_end = (
            timezone.now()
            + relativedelta(months=1)
        )

        user.save(
            update_fields=[
                'is_paid',
                'subscription_end'
            ]
        )

        # Remove payment session
        request.session.pop(
            'payment_started',
            None
        )

        return redirect('home')

    return redirect('first_time')

# =========================================================
# UNLOCK PAGE
# =========================================================

@login_required(login_url='login')
def unlock(request):

    # -----------------------------------------------------
    # Admin
    # -----------------------------------------------------

    if request.user.is_staff or request.user.is_superuser:

        return redirect('admin_panel')


    # -----------------------------------------------------
    # Already paid
    # -----------------------------------------------------

    if request.user.is_paid:

        if request.user.subscription_end is not None:

            if request.user.subscription_end > timezone.now():

                return redirect('home')


    # -----------------------------------------------------
    # Not paid / expired
    # -----------------------------------------------------

    return render(
        request,
        'fit/unlock.html'
    )
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
