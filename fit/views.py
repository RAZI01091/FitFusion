# =========================================================
# IMPORTS
# =========================================================

import random
import time

import razorpay

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

from dateutil.relativedelta import relativedelta

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
# SUBSCRIPTION PAYMENT SETTINGS
# =========================================================

SUBSCRIPTION_AMOUNT = 9
SUBSCRIPTION_AMOUNT_PAISE = SUBSCRIPTION_AMOUNT * 100
SUBSCRIPTION_CURRENCY = "INR"


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

            # Create user
            user = form.save()

            messages.success(
                request,
                'Account created successfully! Please login.'
            )

            # Do NOT login automatically
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

        # Admin
        if request.user.is_staff or request.user.is_superuser:
            return redirect('admin_panel')

        # Paid user
        if request.user.is_paid:
            return redirect('home')

        # Unpaid user
        return redirect('first_time')

    # Login form submitted
    if request.method == 'POST':

        form = LoginForm(request.POST)

        if form.is_valid():

            email = form.cleaned_data.get('email')
            password = form.cleaned_data.get('password')

            # Authenticate
            user = authenticate(
                request,
                email=email,
                password=password
            )

            # User found
            if user is not None:

                # Check account status
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

                # Login
                login(request, user)

                messages.success(
                    request,
                    f'Welcome back, {user.name}!'
                )

                # Admin
                if user.is_staff or user.is_superuser:
                    return redirect('admin_panel')

                # Not paid
                if not user.is_paid:
                    return redirect('first_time')

                # Paid
                return redirect('home')

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

    # Admin can access without payment
    if request.user.is_staff or request.user.is_superuser:

        return render(
            request,
            'fit/home.html'
        )

    # Normal user - not paid
    if not request.user.is_paid:

        return redirect('first_time')

    # Paid user must have subscription end date
    if request.user.subscription_end is None:

        request.user.is_paid = False

        request.user.save(
            update_fields=['is_paid']
        )

        return redirect('first_time')

    # Subscription expired
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

    # Paid and active
    return render(
        request,
        'fit/home.html'
    )


# =========================================================
# FIRST TIME / PREMIUM PAGE
# =========================================================

@login_required(login_url='login')
def first_time(request):

    # Admin does not need Premium
    if request.user.is_staff or request.user.is_superuser:

        return redirect('admin_panel')

    # Already paid
    if request.user.is_paid:

        if (
            request.user.subscription_end
            and
            request.user.subscription_end > timezone.now()
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


# =========================================================
# START RAZORPAY PAYMENT
# =========================================================
@login_required(login_url='login')
def start_payment(request):

    # Admin does not need payment
    if request.user.is_staff or request.user.is_superuser:
        return redirect('admin_panel')

    # Already paid and subscription still active
    if request.user.is_paid:

        if (
            request.user.subscription_end
            and request.user.subscription_end > timezone.now()
        ):
            return redirect('home')

    # Only allow POST
    if request.method != 'POST':
        return redirect('first_time')

    try:

        # -------------------------------------------------
        # Create Razorpay Order
        # -------------------------------------------------

        order_data = {
            'amount': SUBSCRIPTION_AMOUNT_PAISE,
            'currency': SUBSCRIPTION_CURRENCY,
            'receipt': f'fitfusion_{request.user.id}_{int(time.time())}',
            'partial_payment': False,
        }

        razorpay_order = razorpay_client.order.create(
            data=order_data
        )

        # -------------------------------------------------
        # Save payment information in session
        # -------------------------------------------------

        request.session['payment_started'] = True

        request.session['razorpay_order_id'] = (
            razorpay_order['id']
        )

        request.session['razorpay_amount'] = (
            SUBSCRIPTION_AMOUNT_PAISE
        )

        # -------------------------------------------------
        # Razorpay Checkout
        # -------------------------------------------------

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

    except Exception as e:

        import traceback
        traceback.print_exc()

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

    # Only POST request allowed
    if request.method != 'POST':
        return redirect('first_time')

    user = request.user

    # -----------------------------------------------------
    # Get payment details sent by Razorpay Checkout
    # -----------------------------------------------------

    razorpay_payment_id = request.POST.get(
        'razorpay_payment_id'
    )

    razorpay_order_id = request.POST.get(
        'razorpay_order_id'
    )

    razorpay_signature = request.POST.get(
        'razorpay_signature'
    )

    # -----------------------------------------------------
    # Check required values
    # -----------------------------------------------------

    if not all([
        razorpay_payment_id,
        razorpay_order_id,
        razorpay_signature,
    ]):

        messages.error(
            request,
            'Payment information is missing.'
        )

        return redirect('first_time')

    # -----------------------------------------------------
    # Check that order belongs to this session
    # -----------------------------------------------------

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

        # -------------------------------------------------
        # Verify Razorpay Signature
        # -------------------------------------------------

        payment_data = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature,
        }

        razorpay_client.utility.verify_payment_signature(
            payment_data
        )

        # -------------------------------------------------
        # Fetch order from Razorpay
        # -------------------------------------------------

        razorpay_order = razorpay_client.order.fetch(
            razorpay_order_id
        )

        # -------------------------------------------------
        # Verify order amount
        # -------------------------------------------------

        if (
            razorpay_order['amount']
            != SUBSCRIPTION_AMOUNT_PAISE
        ):

            messages.error(
                request,
                'Invalid payment amount.'
            )

            return redirect('first_time')

        # -------------------------------------------------
        # Verify order currency
        # -------------------------------------------------

        if (
            razorpay_order['currency']
            != SUBSCRIPTION_CURRENCY
        ):

            messages.error(
                request,
                'Invalid payment currency.'
            )

            return redirect('first_time')

        # -------------------------------------------------
        # Fetch payment from Razorpay
        # -------------------------------------------------

        payment = razorpay_client.payment.fetch(
            razorpay_payment_id
        )

        # -------------------------------------------------
        # Verify payment belongs to this order
        # -------------------------------------------------

        if payment.get('order_id') != razorpay_order_id:

            messages.error(
                request,
                'Payment does not belong to this order.'
            )

            return redirect('first_time')

        # -------------------------------------------------
        # Check payment amount
        # -------------------------------------------------

        if (
            payment['amount']
            != SUBSCRIPTION_AMOUNT_PAISE
        ):

            messages.error(
                request,
                'Payment amount verification failed.'
            )

            return redirect('first_time')

        # -------------------------------------------------
        # Check payment currency
        # -------------------------------------------------

        if (
            payment['currency']
            != SUBSCRIPTION_CURRENCY
        ):

            messages.error(
                request,
                'Payment currency verification failed.'
            )

            return redirect('first_time')

        # -------------------------------------------------
        # Check payment status
        # -------------------------------------------------

        payment_status = payment.get('status')

        if payment_status != 'captured':

            messages.error(
                request,
                'Payment was not captured successfully.'
            )

            return redirect('first_time')

        # =================================================
        # PAYMENT VERIFIED SUCCESSFULLY
        # =================================================

        now = timezone.now()

        # -------------------------------------------------
        # Calculate subscription end date
        # -------------------------------------------------

        if (
            user.subscription_end
            and user.subscription_end > now
        ):
            # Existing active subscription
            subscription_end = (
                user.subscription_end
                + relativedelta(months=1)
            )

        else:
            # New subscription or expired subscription
            subscription_end = (
                now
                + relativedelta(months=1)
            )

        # -------------------------------------------------
        # Activate Premium
        # -------------------------------------------------

        user.is_paid = True

        user.subscription_start = now

        user.subscription_end = subscription_end

        # -------------------------------------------------
        # Save Razorpay payment details
        # -------------------------------------------------

        user.razorpay_order_id = razorpay_order_id

        user.razorpay_payment_id = razorpay_payment_id

        user.razorpay_signature = razorpay_signature

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

        # -------------------------------------------------
        # Clear payment session
        # -------------------------------------------------

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

        # -------------------------------------------------
        # Success message
        # -------------------------------------------------

        messages.success(
            request,
            'Payment successful! '
            'Your Premium subscription is now active.'
        )

        return redirect('home')

    # -----------------------------------------------------
    # Razorpay signature error
    # -----------------------------------------------------

    except razorpay.errors.SignatureVerificationError:

        messages.error(
            request,
            'Payment verification failed. '
            'Invalid payment signature.'
        )

        return redirect('first_time')

    # -----------------------------------------------------
    # Other Razorpay errors
    # -----------------------------------------------------

    except Exception as e:

        print(
            "Razorpay payment verification error:",
            e
        )

        messages.error(
            request,
            'Payment verification failed. '
            'Please contact support if money was deducted.'
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

    # Already paid
    if request.user.is_paid:

        if request.user.subscription_end is not None:

            if (
                request.user.subscription_end
                > timezone.now()
            ):

                return redirect('home')

    # Not paid / expired
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


def admin_panel_view(request):

    users = User.objects.all().order_by('-id')

    total_users = users.count()

    male_users = users.filter(
        gender='M'
    ).count()

    female_users = users.filter(
        gender='F'
    ).count()

    other_users = users.filter(
        gender='O'
    ).count()

    # Premium and Normal users
    premium_users = users.filter(
        is_premium=True
    ).count()

    normal_users = users.filter(
        is_premium=False
    ).count()

    ages = [
        u.age
        for u in users
        if u.age is not None
    ]

    avg_age = (
        sum(ages) / len(ages)
        if ages
        else 0
    )

    context = {

        'users': users,

        'total_users': total_users,

        'male_users': male_users,

        'female_users': female_users,

        'other_users': other_users,

        'premium_users': premium_users,

        'normal_users': normal_users,

        'avg_age': round(
            avg_age,
            1
        ),
    }

    return render(
        request,
        'fit/admin_panel.html',
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
def toggle_user_status_view(
    request,
    user_id
):

    if request.method == 'POST':

        user_to_toggle = get_object_or_404(
            User,
            id=user_id
        )

        # Do not allow admin to block himself
        if user_to_toggle == request.user:

            messages.error(
                request,
                "You cannot block your own administrative account!"
            )

        else:

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
                form.cleaned_data['email']
                .lower()
            )

            try:

                user = User.objects.get(
                    email__iexact=email
                )

                # Generate 6 digit OTP
                otp = str(
                    random.randint(
                        100000,
                        999999
                    )
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
                        f"Your FitFusion password reset OTP is: "
                        f"{otp}\n\n"
                        f"This OTP is valid for 5 minutes.\n\n"
                        f"If you did not request a password reset, "
                        f"please ignore this email.\n\n"
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

                return redirect(
                    'verify_otp'
                )

            except User.DoesNotExist:

                # Don't reveal whether email exists
                messages.success(
                    request,
                    "If this email is registered, "
                    "an OTP has been sent."
                )

                return redirect(
                    'forgot_password'
                )

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

    # No OTP
    if not reset_email or not stored_otp:

        messages.error(
            request,
            "Please request a new OTP."
        )

        return redirect(
            'forgot_password'
        )

    # Check OTP expiry
    if otp_time:

        elapsed_time = (
            time.time()
            - otp_time
        )

        # 5 minutes
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

            return redirect(
                'forgot_password'
            )

    if request.method == "POST":

        form = VerifyOTPForm(
            request.POST
        )

        if form.is_valid():

            entered_otp = form.cleaned_data['otp']

            if entered_otp == stored_otp:

                request.session[
                    'otp_verified'
                ] = True

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

                return redirect(
                    'reset_password'
                )

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

        return redirect(
            'forgot_password'
        )

    try:

        user = User.objects.get(
            email__iexact=reset_email
        )

    except User.DoesNotExist:

        messages.error(
            request,
            "User account not found."
        )

        return redirect(
            'forgot_password'
        )

    if request.method == "POST":

        form = ResetPasswordForm(
            request.POST
        )

        if form.is_valid():

            new_password = form.cleaned_data[
                'password'
            ]

            # Always use set_password()
            user.set_password(
                new_password
            )

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

            return redirect(
                'login'
            )

    else:

        form = ResetPasswordForm()

    return render(
        request,
        'fit/reset_password.html',
        {'form': form}
    )

