# delete_user.py
import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Dyno.settings')
django.setup()

from django.contrib.auth.models import User

def delete_non_staff_users():
    users_deleted = User.objects.filter(is_staff=False).delete()
    print(f"✅ Deleted {users_deleted[0]} non-staff users.")

if __name__ == "__main__":
    delete_non_staff_users()
