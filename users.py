import os
import django
import random
from datetime import date, timedelta
from django.utils import timezone

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Dyno.settings")
django.setup()

from django.contrib.auth.models import User
from accounts.models import Profile  # import your profile model

cities = ["Raipur", "Bhopal", "Chennai", "Delhi", "Mathura","Mumbai", "Kolkata", "Hyderabad", "Pune", "Bangalore", "Ahmedabad"]
genders = ["Male", "Female"]

for i in range(1, 100):
    name = f"Test User {i}"
    username = f"user{i}"
    email = f"user{i}@gmail.com"
    password = "678910"
    gender = random.choice(genders)
    city = random.choice(cities)
    dob = date(1995, 1, 1) + timedelta(days=random.randint(0, 10000))  # random DOB between 1995 and ~2023

    if not User.objects.filter(username=username).exists():
        user = User.objects.create_user(username=username, email=email, password=password,first_name=name.split()[0],)
        
        # Create profile
        Profile.objects.create(
            user=user,
            gender=gender,
            city=city,
            dob=dob
        )

print(f"✅ Successfully created {i} users with full profile.")
