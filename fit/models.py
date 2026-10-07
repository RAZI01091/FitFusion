from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models


class CustomUserManager(BaseUserManager):

    def create_user(self, email, name, password=None, **extra_fields):

        if not email:
            raise ValueError('Users must have an email address')

        email = self.normalize_email(email)

        user = self.model(
            email=email,
            name=name,
            **extra_fields
        )

        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, email, name, password=None, **extra_fields):

        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(
                'Superuser must have is_staff=True.'
            )

        if extra_fields.get('is_superuser') is not True:
            raise ValueError(
                'Superuser must have is_superuser=True.'
            )

        return self.create_user(
            email,
            name,
            password,
            **extra_fields
        )


class CustomUser(AbstractBaseUser, PermissionsMixin):

    # -------------------------
    # USER INFORMATION
    # -------------------------

    email = models.EmailField(unique=True)

    name = models.CharField(max_length=255)

    age = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    GENDER_CHOICES = (
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    )

    gender = models.CharField(
        max_length=1,
        choices=GENDER_CHOICES,
        null=True,
        blank=True
    )

    # -------------------------
    # ACCOUNT STATUS
    # -------------------------

    is_active = models.BooleanField(default=True)

    is_staff = models.BooleanField(default=False)

    # -------------------------
    # PREMIUM / SUBSCRIPTION
    # -------------------------

    is_paid = models.BooleanField(default=False)

    subscription_start = models.DateTimeField(
        null=True,
        blank=True
    )

    subscription_end = models.DateTimeField(
        null=True,
        blank=True
    )

    # -------------------------
    # MANAGER
    # -------------------------

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'

    REQUIRED_FIELDS = ['name']

    def __str__(self):
        return self.email