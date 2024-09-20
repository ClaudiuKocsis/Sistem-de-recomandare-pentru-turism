from django.core.management.base import BaseCommand
from django.db import connection
from hotelsapp.models import HotelOverallRating, Hotel

class Command(BaseCommand):
    help = 'Populate overall ratings for hotels'

    def handle(self, *args, **kwargs):
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    offering_id, 
                    COUNT(*) as num_reviews,
                    AVG(CAST(ratings->>'overall' AS FLOAT)) as average_overall_rating
                FROM 
                    hotelsapp_review
                GROUP BY 
                    offering_id
            """)
            results = cursor.fetchall()

        for offering_id, num_reviews, average_overall_rating in results:
            hotel = Hotel.objects.get(id=offering_id)
            HotelOverallRating.objects.update_or_create(
                hotel=hotel,
                offering_id=offering_id,
                defaults={
                    'average_overall_rating': average_overall_rating,
                    'num_reviews': num_reviews
                }
            )

        self.stdout.write(self.style.SUCCESS('Successfully populated overall ratings'))
