from django.db import models

class Book(models.Model):
    title = models.CharField(max_length=200)
    author = models.CharField(max_length=200)
    category = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=6, decimal_places=2)
    cover_image = models.URLField()
    published_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)  # Timestamp for creation

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-created_at']

class Purchase(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    user_email = models.EmailField()
    fullname = models.CharField(max_length=255)  # Field for the user's name
    phone_number = models.CharField(max_length=15)  # Field for the user's phone number
    address = models.CharField(max_length=255)  # Field for the user's address
    zip_code = models.CharField(max_length=10)  # Field for the user's zip code
    purchase_date = models.DateTimeField(auto_now_add=True)  # Timestamp for purchase
    delivered = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.fullname} ({self.user_email}) purchased {self.book.title} on {self.purchase_date}"

    class Meta:
        ordering = ['-purchase_date']