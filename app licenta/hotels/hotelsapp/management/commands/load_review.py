import csv
import json
import psycopg2
import ast
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = 'Load review data from reviews.csv into the database'

    def handle(self, *args, **kwargs):
        self.load_reviews()

    def sanitize_json(self, json_str):
        """
        Sanitize JSON string by converting it using ast.literal_eval
        and then dumping it back to a JSON string.
        """
        try:
            json_obj = ast.literal_eval(json_str)
            return json.dumps(json_obj)
        except (ValueError, SyntaxError) as e:
            self.stdout.write(self.style.ERROR(f"Error sanitizing JSON string: {json_str} - {e}"))
            return '{}'

    def load_reviews(self):
        conn = psycopg2.connect(
            dbname=settings.DATABASES['default']['NAME'],
            user=settings.DATABASES['default']['USER'],
            password=settings.DATABASES['default']['PASSWORD'],
            host=settings.DATABASES['default']['HOST'],
            port=settings.DATABASES['default']['PORT']
        )
        conn.autocommit = True
        cursor = conn.cursor()

        with open(r'D:\app licenta\reviews.csv', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                try:
                    # Sanitize the JSON fields
                    ratings_str = self.sanitize_json(row['ratings'])
                    author_str = self.sanitize_json(row['author'])
                    
                    # Parse JSON fields
                    ratings = json.loads(ratings_str)
                    author = json.loads(author_str)
                except json.JSONDecodeError as e:
                    self.stdout.write(self.style.ERROR(f"Error parsing JSON in row {row}: {e}"))
                    continue

                # Check if the hotel exists
                cursor.execute("SELECT id FROM hotelsapp_hotel WHERE id = %s", (row['offering_id'],))
                hotel_id = cursor.fetchone()
                if not hotel_id:
                    self.stdout.write(self.style.ERROR(f"Hotel matching query does not exist for row {row}"))
                    continue

                cursor.execute(
                    """
                    INSERT INTO hotelsapp_review (id, hotel_id, ratings, title, text, author, date_stayed, offering_id, num_helpful_votes, date, via_mobile)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (row['id'], row['offering_id'], json.dumps(ratings), row['title'], row['text'], json.dumps(author), row['date_stayed'], row['offering_id'], row['num_helpful_votes'], row['date'], row['via_mobile'].lower() == 'true')
                )
                self.stdout.write(self.style.SUCCESS(f"Successfully inserted Review: {row['title']} (ID: {row['id']})"))

        cursor.close()
        conn.close()
