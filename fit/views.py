# =========================================================
# IMPORTS
# =========================================================

import random
import time
import logging
import razorpay
from django.db.models import Avg, Q

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    login,
    logout,
    get_user_model,
)
from django.contrib.auth.decorators import (
    login_required,
    user_passes_test,
)
from django.core.mail import send_mail
from django.shortcuts import (
    render,
    redirect,
    get_object_or_404,
)
from django.utils import timezone
from django.views.decorators.cache import never_cache

from .forms import (
    SignupForm,
    LoginForm,
    ForgotPasswordForm,
    VerifyOTPForm,
    ResetPasswordForm,
)


# =========================================================
# USER MODEL
# =========================================================

User = get_user_model()


# =========================================================
# RAZORPAY CLIENT
# =========================================================

razorpay_client = razorpay.Client(
    auth=(
        settings.RAZORPAY_KEY_ID,
        settings.RAZORPAY_KEY_SECRET,
    )
)


# =========================================================
# LIFETIME PREMIUM PAYMENT SETTINGS
# =========================================================

SUBSCRIPTION_AMOUNT = 9
SUBSCRIPTION_AMOUNT_PAISE = SUBSCRIPTION_AMOUNT * 100
SUBSCRIPTION_CURRENCY = "INR"


# =========================================================
# WEBSITE ENTRY
# =========================================================

def entry_view(request):

    # User is not logged in
    if not request.user.is_authenticated:
        return redirect('login')

    # Admin / Staff
    if request.user.is_staff or request.user.is_superuser:
        return redirect('admin_panel')

    # Lifetime Premium user
    if request.user.is_paid:
        return redirect('home')

    # Normal user
    return redirect('first_time')


# =========================================================
# SIGNUP
# =========================================================

def signup_view(request):

    # Already logged in
    if request.user.is_authenticated:

        # Admin
        if request.user.is_staff or request.user.is_superuser:
            return redirect('admin_panel')

        # Lifetime Premium user
        if request.user.is_paid:
            return redirect('home')

        # Normal user
        return redirect('first_time')

    if request.method == 'POST':

        form = SignupForm(request.POST)

        if form.is_valid():

            form.save()

            messages.success(
                request,
                'Account created successfully! Please login.'
            )

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

    # Already logged in
    if request.user.is_authenticated:

        # Admin
        if request.user.is_staff or request.user.is_superuser:
            return redirect('admin_panel')

        # Lifetime Premium
        if request.user.is_paid:
            return redirect('home')

        # Normal user
        return redirect('first_time')

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

            if user is not None:

                # Blocked account
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

                # Login user
                login(request, user)

                messages.success(
                    request,
                    f'Welcome back, {user.name}!'
                )

                # Admin
                if user.is_staff or user.is_superuser:
                    return redirect('admin_panel')

                # Lifetime Premium
                if user.is_paid:
                    return redirect('home')

                # Normal user
                return redirect('first_time')

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

    # Admin
    if request.user.is_staff or request.user.is_superuser:
        return redirect('admin_panel')

    # Normal user without Premium
    if not request.user.is_paid:
        return redirect('first_time')

    # Lifetime Premium user
    return render(
        request,
        'fit/home.html'
    )


# =========================================================
# FIRST TIME / PREMIUM PAGE
# =========================================================

@login_required(login_url='login')
def first_time(request):

    # Admin
    if request.user.is_staff or request.user.is_superuser:
        return redirect('admin_panel')

    # Already has lifetime Premium
    if request.user.is_paid:
        return redirect('home')

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


# =========================================================
# START RAZORPAY PAYMENT
# =========================================================

@login_required(login_url='login')
def start_payment(request):

    # Admin does not need payment
    if request.user.is_staff or request.user.is_superuser:
        return redirect('admin_panel')

    # Lifetime Premium users cannot purchase again
    if request.user.is_paid:
        return redirect('home')

    # Only POST requests allowed
    if request.method != 'POST':
        return redirect('first_time')

    try:

        # Create Razorpay order
        order_data = {
            'amount': SUBSCRIPTION_AMOUNT_PAISE,
            'currency': SUBSCRIPTION_CURRENCY,
            'receipt': (
                f'fitfusion_{request.user.id}_'
                f'{int(time.time())}'
            ),
            'partial_payment': False,
        }

        razorpay_order = razorpay_client.order.create(
            data=order_data
        )

        # Store payment details in session
        request.session['payment_started'] = True

        request.session['razorpay_order_id'] = (
            razorpay_order['id']
        )

        request.session['razorpay_amount'] = (
            SUBSCRIPTION_AMOUNT_PAISE
        )

        # Razorpay Checkout context
        context = {
            'razorpay_key_id': settings.RAZORPAY_KEY_ID,
            'razorpay_order_id': razorpay_order['id'],
            'razorpay_amount': SUBSCRIPTION_AMOUNT_PAISE,
            'razorpay_amount_display': SUBSCRIPTION_AMOUNT,
            'razorpay_currency': SUBSCRIPTION_CURRENCY,
            'user_name': request.user.name,
            'user_email': request.user.email,
        }

        return render(
            request,
            'fit/payment.html',
            context
        )

    except Exception:

        logger = logging.getLogger(__name__)

        logger.exception(
            'Unable to start Razorpay payment.'
        )

        messages.error(
            request,
            'Unable to start payment. Please try again.'
        )

        return redirect('first_time')


# =========================================================
# VERIFY RAZORPAY PAYMENT
# =========================================================

@login_required(login_url='login')
def confirm_payment(request):

    # Only POST requests allowed
    if request.method != 'POST':

        messages.error(
            request,
            'Invalid payment request. Please try again.'
        )

        return redirect('first_time')

    user = request.user

    # Admin does not need payment
    if user.is_staff or user.is_superuser:
        return redirect('admin_panel')

    # Do not process another payment for a user
    # who already has lifetime Premium
    if user.is_paid:
        return redirect('home')

    # Get Razorpay payment details
    razorpay_payment_id = request.POST.get(
        'razorpay_payment_id'
    )

    razorpay_order_id = request.POST.get(
        'razorpay_order_id'
    )

    razorpay_signature = request.POST.get(
        'razorpay_signature'
    )

    # Check required values
    if not all([
        razorpay_payment_id,
        razorpay_order_id,
        razorpay_signature,
    ]):

        messages.error(
            request,
            'Payment information is missing. Please try again.'
        )

        return redirect('first_time')

    # Verify session order
    session_order_id = request.session.get(
        'razorpay_order_id'
    )

    if not session_order_id:

        messages.error(
            request,
            'Payment session expired. Please try again.'
        )

        return redirect('first_time')

    if razorpay_order_id != session_order_id:

        messages.error(
            request,
            'Invalid payment order.'
        )

        return redirect('first_time')

    try:

        # Verify Razorpay signature
        payment_data = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature,
        }

        razorpay_client.utility.verify_payment_signature(
            payment_data
        )

        # Fetch Razorpay order
        razorpay_order = razorpay_client.order.fetch(
            razorpay_order_id
        )

        # Verify order amount
        if (
            razorpay_order.get('amount')
            != SUBSCRIPTION_AMOUNT_PAISE
        ):

            messages.error(
                request,
                'Payment amount verification failed.'
            )

            return redirect('first_time')

        # Verify order currency
        if (
            razorpay_order.get('currency')
            != SUBSCRIPTION_CURRENCY
        ):

            messages.error(
                request,
                'Payment currency verification failed.'
            )

            return redirect('first_time')

        # Fetch payment details
        payment = razorpay_client.payment.fetch(
            razorpay_payment_id
        )

        # Verify payment belongs to this order
        if payment.get('order_id') != razorpay_order_id:

            messages.error(
                request,
                'Payment does not belong to this order.'
            )

            return redirect('first_time')

        # Verify payment amount
        if (
            payment.get('amount')
            != SUBSCRIPTION_AMOUNT_PAISE
        ):

            messages.error(
                request,
                'Payment amount verification failed.'
            )

            return redirect('first_time')

        # Verify payment currency
        if (
            payment.get('currency')
            != SUBSCRIPTION_CURRENCY
        ):

            messages.error(
                request,
                'Payment currency verification failed.'
            )

            return redirect('first_time')

        # Verify captured payment status
        if payment.get('status') != 'captured':

            messages.error(
                request,
                'Payment has not been captured successfully.'
            )

            return redirect('first_time')

        # =========================================
        # ACTIVATE LIFETIME PREMIUM
        # =========================================

        now = timezone.now()

        # Grant lifetime access
        user.is_paid = True

        # Record activation date
        user.subscription_start = now

        # Lifetime Premium has no expiry date
        user.subscription_end = None

        # Save Razorpay payment details
        user.razorpay_order_id = razorpay_order_id
        user.razorpay_payment_id = razorpay_payment_id
        user.razorpay_signature = razorpay_signature

        # Save to database
        user.save(
            update_fields=[
                'is_paid',
                'subscription_start',
                'subscription_end',
                'razorpay_order_id',
                'razorpay_payment_id',
                'razorpay_signature',
            ]
        )

        # Clear payment session
        request.session.pop(
            'payment_started',
            None
        )

        request.session.pop(
            'razorpay_order_id',
            None
        )

        request.session.pop(
            'razorpay_amount',
            None
        )

        # Success message
        messages.success(
            request,
            'Payment successful! '
            'Your Lifetime Premium access is now active.'
        )

        # Redirect to home
        return redirect('home')

    except razorpay.errors.SignatureVerificationError:

        messages.error(
            request,
            'Payment verification failed. Invalid signature.'
        )

        return redirect('first_time')

    except Exception:

        logger = logging.getLogger(__name__)

        logger.exception(
            'Razorpay payment verification failed.'
        )

        messages.error(
            request,
            'Unable to verify payment. Please check your '
            'payment status or contact support.'
        )

        return redirect('first_time')


# =========================================================
# UNLOCK PAGE
# =========================================================

@login_required(login_url='login')
def unlock(request):

    # Admin
    if request.user.is_staff or request.user.is_superuser:
        return redirect('admin_panel')

    # Lifetime Premium user
    if request.user.is_paid:
        return redirect('home')

    # Normal user
    return render(
        request,
        'fit/unlock.html'
    )


# =========================================================
# ADMIN PANEL
# =========================================================

@login_required(login_url='login')
@user_passes_test(
    lambda u: u.is_staff or u.is_superuser,
    login_url='home'
)





@login_required
def admin_panel_view(request):

    # ==========================================
    # SECURITY: ADMIN ACCESS ONLY
    # ==========================================

    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(
            request,
            "You are not authorized to access the admin panel."
        )
        return redirect("home")

    # ==========================================
    # GET ALL USERS
    # ==========================================

    all_users = User.objects.all().order_by("-id")

    # ==========================================
    # TOTAL USER STATISTICS
    # ==========================================

    total_users = all_users.count()

    male_users = all_users.filter(gender="M").count()

    female_users = all_users.filter(gender="F").count()

    other_users = all_users.filter(gender="O").count()

    premium_users = all_users.filter(is_paid=True).count()

    normal_users = all_users.filter(
        is_paid=False,
        is_staff=False,
        is_superuser=False
    ).count()

    # ==========================================
    # AVERAGE AGE
    # ==========================================

    avg_age = all_users.aggregate(
        average_age=Avg("age")
    )["average_age"]

    avg_age = round(avg_age, 1) if avg_age is not None else 0

    # ==========================================
    # SEARCH BY NAME OR EMAIL
    # ==========================================

    search_query = request.GET.get("search", "").strip()

    users = all_users

    if search_query:
        users = users.filter(
            Q(name__icontains=search_query)
            | Q(email__icontains=search_query)
        )

    # ==========================================
    # FILTER BY ACCOUNT TYPE
    # ==========================================

    account_type = request.GET.get(
        "account_type",
        "all"
    ).strip().lower()

    if account_type == "premium":

        users = users.filter(is_paid=True)

    elif account_type == "normal":

        users = users.filter(
            is_paid=False,
            is_staff=False,
            is_superuser=False
        )

    # ==========================================
    # FILTER BY ACCOUNT STATUS
    # ==========================================

    status_filter = request.GET.get(
        "status",
        "all"
    ).strip().lower()

    if status_filter == "active":

        users = users.filter(is_active=True)

    elif status_filter == "blocked":

        users = users.filter(is_active=False)

    # ==========================================
    # FINAL FILTERED USER LIST
    # ==========================================

    users = users.distinct().order_by("-id")

    # ==========================================
    # CONTEXT
    # ==========================================

    context = {
        "users": users,

        # Overall statistics
        "total_users": total_users,
        "male_users": male_users,
        "female_users": female_users,
        "other_users": other_users,
        "premium_users": premium_users,
        "normal_users": normal_users,
        "avg_age": avg_age,

        # Search and filter values
        "search_query": search_query,
        "account_type": account_type,
        "status_filter": status_filter,
    }

    return render(
        request,
        "fit/admin_panel.html",
        context
    )




# =========================================================
# TOGGLE USER STATUS
# =========================================================

@login_required(login_url='login')
@user_passes_test(
    lambda u: u.is_staff or u.is_superuser,
    login_url='home'
)
def toggle_user_status_view(request, user_id):

    if request.method == 'POST':

        user_to_toggle = get_object_or_404(
            User,
            id=user_id
        )

        # Do not block admin's own account
        if user_to_toggle == request.user:

            messages.error(
                request,
                "You cannot block your own "
                "administrative account!"
            )

        else:

            # Toggle active status
            user_to_toggle.is_active = (
                not user_to_toggle.is_active
            )

            user_to_toggle.save()

            status = (
                "blocked"
                if not user_to_toggle.is_active
                else "unblocked"
            )

            messages.success(
                request,
                f"User {user_to_toggle.name} "
                f"has been {status} successfully."
            )

    return redirect('admin_panel')


# =========================================================
# FORGOT PASSWORD
# =========================================================

@never_cache
def forgot_password(request):

    if request.method == "POST":

        form = ForgotPasswordForm(
            request.POST
        )

        if form.is_valid():

            email = (
                form.cleaned_data['email'].lower()
            )

            try:

                user = User.objects.get(
                    email__iexact=email
                )

                # Generate six-digit OTP
                otp = str(
                    random.randint(100000, 999999)
                )

                # Store reset information
                request.session['reset_email'] = email
                request.session['reset_otp'] = otp
                request.session['reset_otp_time'] = time.time()

                # Send email
                send_mail(
                    subject="FitFusion Password Reset OTP",

                    message=(
                        f"Hello,\n\n"
                        f"Your FitFusion password "
                        f"reset OTP is: {otp}\n\n"
                        f"This OTP is valid for 5 minutes.\n\n"
                        f"If you did not request a "
                        f"password reset, please ignore "
                        f"this email.\n\n"
                        f"Regards,\n"
                        f"FitFusion Team"
                    ),

                    from_email=settings.DEFAULT_FROM_EMAIL,

                    recipient_list=[
                        user.email
                    ],

                    fail_silently=False,
                )

                messages.success(
                    request,
                    "OTP has been sent to your email."
                )

                return redirect('verify_otp')

            except User.DoesNotExist:

                # Do not reveal whether the email exists
                messages.success(
                    request,
                    "If this email is registered, "
                    "an OTP has been sent."
                )

                return redirect('forgot_password')

    else:
        form = ForgotPasswordForm()

    return render(
        request,
        'fit/forgot_password.html',
        {'form': form}
    )


# =========================================================
# VERIFY OTP
# =========================================================

@never_cache
def verify_otp(request):

    reset_email = request.session.get(
        'reset_email'
    )

    stored_otp = request.session.get(
        'reset_otp'
    )

    otp_time = request.session.get(
        'reset_otp_time'
    )

    # No OTP available
    if not reset_email or not stored_otp:

        messages.error(
            request,
            "Please request a new OTP."
        )

        return redirect('forgot_password')

    # Check OTP expiry
    if otp_time:

        elapsed_time = time.time() - otp_time

        # Five minutes
        if elapsed_time > 300:

            request.session.pop(
                'reset_otp',
                None
            )

            request.session.pop(
                'reset_otp_time',
                None
            )

            messages.error(
                request,
                "OTP has expired. "
                "Please request a new OTP."
            )

            return redirect('forgot_password')

    # Verify OTP
    if request.method == "POST":

        form = VerifyOTPForm(
            request.POST
        )

        if form.is_valid():

            entered_otp = form.cleaned_data['otp']

            if entered_otp == stored_otp:

                request.session['otp_verified'] = True

                # OTP cannot be reused
                request.session.pop(
                    'reset_otp',
                    None
                )

                request.session.pop(
                    'reset_otp_time',
                    None
                )

                messages.success(
                    request,
                    "OTP verified successfully."
                )

                return redirect('reset_password')

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


# =========================================================
# RESET PASSWORD
# =========================================================

@never_cache
def reset_password(request):

    reset_email = request.session.get(
        'reset_email'
    )

    otp_verified = request.session.get(
        'otp_verified'
    )

    # OTP not verified
    if not reset_email or not otp_verified:

        messages.error(
            request,
            "Please verify your OTP first."
        )

        return redirect('forgot_password')

    # Find user
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

    # Reset password
    if request.method == "POST":

        form = ResetPasswordForm(
            request.POST
        )

        if form.is_valid():

            new_password = form.cleaned_data['password']

            # Always use set_password()
            user.set_password(new_password)
            user.save()

            # Clear password reset session
            request.session.pop(
                'reset_email',
                None
            )

            request.session.pop(
                'otp_verified',
                None
            )

            request.session.pop(
                'reset_otp',
                None
            )

            request.session.pop(
                'reset_otp_time',
                None
            )

            messages.success(
                request,
                "Password reset successfully. "
                "Please login."
            )

            return redirect('login')

    else:
        form = ResetPasswordForm()

    return render(
        request,
        'fit/reset_password.html',
        {'form': form}
    )


# =========================================================
# TEMPORARY LIVE DATABASE EXPORT
# Remove this code after completing the migration.
# =========================================================

import io
from django.core.management import call_command
from django.http import HttpResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.cache import never_cache


@staff_member_required
@never_cache
def temporary_database_export(request):
    if request.method != "GET":
        return HttpResponse(
            "Method not allowed",
            status=405
        )

    output = io.StringIO()

    call_command(
        "dumpdata",
        natural_foreign=True,
        natural_primary=True,
        exclude=[
            "contenttypes",
            "auth.permission",
            "sessions.session",
        ],
        indent=2,
        stdout=output,
    )

    response = HttpResponse(
        output.getvalue(),
        content_type="application/json",
    )

    response["Content-Disposition"] = (
        'attachment; filename="fitfusion_live_backup.json"'
    )

    response["Cache-Control"] = "no-store"

    return response

