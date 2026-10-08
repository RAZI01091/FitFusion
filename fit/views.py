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
from django.contrib import messages
from django.conf import settings

from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from .forms import (ForgotPasswordForm,VerifyOTPForm,ResetPasswordForm)
from django.views.decorators.cache import never_cache
import random



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
    # ADMIN CAN ACCESS HOME WITHOUT PAYMENT
    # -----------------------------------------------------

    if request.user.is_staff or request.user.is_superuser:
        return render(
            request,
            'fit/home.html'
        )


    # -----------------------------------------------------
    # NORMAL USER - NOT PAID
    # -----------------------------------------------------

    if not request.user.is_paid:

        return redirect('first_time')


    # -----------------------------------------------------
    # PAID USER MUST HAVE SUBSCRIPTION END DATE
    # -----------------------------------------------------

    if request.user.subscription_end is None:

        request.user.is_paid = False

        request.user.save(
            update_fields=['is_paid']
        )

        return redirect('first_time')


    # -----------------------------------------------------
    # SUBSCRIPTION EXPIRED
    # -----------------------------------------------------

    if request.user.subscription_end <= timezone.now():

        request.user.is_paid = False
        request.user.subscription_end = None

        request.user.save(
            update_fields=[
                'is_paid',
                'subscription_end'
            ]
        )

        messages.warning(
            request,
            'Your Premium subscription has expired. '
            'Please renew to continue.'
        )

        return redirect('first_time')


    # -----------------------------------------------------
    # NORMAL USER - PAID AND ACTIVE
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




@never_cache
def forgot_password(request):

    if request.method == "POST":

        form = ForgotPasswordForm(request.POST)

        if form.is_valid():

            email = form.cleaned_data['email'].lower()

            try:
                user = User.objects.get(email__iexact=email)

                # Generate 6 digit OTP
                otp = str(random.randint(100000, 999999))

                # Store temporary information in session
                request.session['reset_email'] = email
                request.session['reset_otp'] = otp

                # OTP expiry: 5 minutes
                request.session['reset_otp_time'] = __import__('time').time()

                # Send email
                send_mail(
                    subject="FitFusion Password Reset OTP",
                    message=(
                        f"Hello,\n\n"
                        f"Your FitFusion password reset OTP is: {otp}\n\n"
                        f"This OTP is valid for 5 minutes.\n\n"
                        f"If you did not request a password reset, "
                        f"please ignore this email.\n\n"
                        f"Regards,\n"
                        f"FitFusion Team"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )

                messages.success(
                    request,
                    "OTP has been sent to your email."
                )

                return redirect('verify_otp')

            except User.DoesNotExist:

                # Don't reveal whether email exists
                messages.success(
                    request,
                    "If this email is registered, an OTP has been sent."
                )

                return redirect('forgot_password')

    else:
        form = ForgotPasswordForm()

    return render(
        request,
        'fit/forgot_password.html',
        {'form': form}
    )



@never_cache
def verify_otp(request):

    reset_email = request.session.get('reset_email')
    stored_otp = request.session.get('reset_otp')
    otp_time = request.session.get('reset_otp_time')

    if not reset_email or not stored_otp:
        messages.error(
            request,
            "Please request a new OTP."
        )
        return redirect('forgot_password')

    # Check OTP expiry
    import time

    if otp_time:

        elapsed_time = time.time() - otp_time

        if elapsed_time > 300:  # 5 minutes

            request.session.pop('reset_otp', None)
            request.session.pop('reset_otp_time', None)

            messages.error(
                request,
                "OTP has expired. Please request a new OTP."
            )

            return redirect('forgot_password')

    if request.method == "POST":

        form = VerifyOTPForm(request.POST)

        if form.is_valid():

            entered_otp = form.cleaned_data['otp']

            if entered_otp == stored_otp:

                request.session['otp_verified'] = True

                # OTP cannot be reused
                request.session.pop('reset_otp', None)
                request.session.pop('reset_otp_time', None)

                messages.success(
                    request,
                    "OTP verified successfully."
                )

                return redirect('reset_password')

            else:

                messages.error(
                    request,
                    "Invalid OTP."
                )

    else:
        form = VerifyOTPForm()

    return render(
        request,
        'fit/verify_otp.html',
        {'form': form}
    )


@never_cache
def reset_password(request):

    reset_email = request.session.get('reset_email')
    otp_verified = request.session.get('otp_verified')

    if not reset_email or not otp_verified:

        messages.error(
            request,
            "Please verify your OTP first."
        )

        return redirect('forgot_password')

    try:
        user = User.objects.get(
            email__iexact=reset_email
        )

    except User.DoesNotExist:

        messages.error(
            request,
            "User account not found."
        )

        return redirect('forgot_password')

    if request.method == "POST":

        form = ResetPasswordForm(request.POST)

        if form.is_valid():

            new_password = form.cleaned_data['password']

            # IMPORTANT
            # Always use set_password()
            user.set_password(new_password)
            user.save()

            # Clear password reset session
            request.session.pop('reset_email', None)
            request.session.pop('otp_verified', None)
            request.session.pop('reset_otp', None)
            request.session.pop('reset_otp_time', None)

            messages.success(
                request,
                "Password reset successfully. Please login."
            )

            return redirect('login')

    else:
        form = ResetPasswordForm()

    return render(
        request,
        'fit/reset_password.html',
        {'form': form}
    )