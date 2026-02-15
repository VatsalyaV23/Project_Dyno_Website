from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class FoodItem(models.Model):
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=7, decimal_places=2)
    image = models.ImageField(upload_to='food_images/')
    description = models.TextField(default="Delicious food item from DYNO.")
    created_at = models.DateTimeField(default=timezone.now)
    added_by = models.ForeignKey(User, on_delete=models.CASCADE)
    city = models.CharField(max_length=100, null=True, blank=True)
    def __str__(self):
        return self.name

class CartItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    image_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    def image_url(self):
        return f"/static/accounts/images/{self.image_name}"
    def __str__(self):
        return f"{self.image_name} x {self.quantity}"

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    gender = models.CharField(max_length=10, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    dob = models.DateField(null=True, blank=True)
    is_staff_member = models.BooleanField(default=False)
    username = models.CharField(max_length=150, null=True, blank=True)
    def __str__(self):
        return f"{self.user.username}'s profile"

class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    food_item = models.ForeignKey(FoodItem, on_delete=models.CASCADE, default=1)
    quantity = models.PositiveIntegerField(default=1)
    address = models.TextField()
    delivery_time = models.TimeField(null=True, blank=True)
    payment_method = models.CharField(max_length=50, default='Cash on Delivery')
    placed_at = models.DateTimeField(auto_now_add=True)
    item_name = models.CharField(max_length=100, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    image = models.ImageField(upload_to='orders/', null=True, blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # price × quantity
    timestamp = models.DateTimeField(default=timezone.now)
    estimated_delivery_minutes = models.IntegerField(default=30)
    name = models.CharField(max_length=255, null=True, blank=True)    # User's name
    gender = models.CharField(max_length=10, null=True, blank=True)   # User's gender
    city = models.CharField(max_length=100, null=True, blank=True)    # User's city
    username = models.CharField(max_length=150, null=True, blank=True)  # User's username
    def __str__(self):
        return f"{self.user.username} ordered {self.food_item.name}"