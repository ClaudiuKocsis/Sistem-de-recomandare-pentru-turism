from django.db import models

class Hotel(models.Model):
    name = models.CharField(max_length=255)
    address = models.JSONField()
    region_id = models.IntegerField(null=True, blank=True)
    url = models.URLField()
    phone = models.CharField(max_length=20)
    hotel_class = models.FloatField()
    details = models.JSONField()
    type = models.CharField(max_length=50)
    id = models.IntegerField(primary_key=True)

    def __str__(self):
        return self.name

class Review(models.Model):
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE)
    ratings = models.JSONField()
    title = models.CharField(max_length=255)
    text = models.TextField()
    author = models.JSONField()
    date_stayed = models.CharField(max_length=50)
    offering_id = models.IntegerField()
    num_helpful_votes = models.IntegerField(default=0)
    date = models.DateField()
    via_mobile = models.BooleanField(default=False)

    def __str__(self):
        return self.title

class HotelOverallRating(models.Model):
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name='overall_ratings')
    offering_id = models.IntegerField()
    num_reviews = models.IntegerField()
    average_overall_rating = models.FloatField()

    def __str__(self):
        return f"Offering {self.offering_id}: {self.average_overall_rating} ({self.num_reviews} reviews)"
