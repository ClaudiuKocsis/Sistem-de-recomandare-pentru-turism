from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from .models import Hotel, Review, HotelOverallRating
from django.utils import timezone

class HotelViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        self.hotel = Hotel.objects.create(
            name="Test Hotel",
            address={
                "street-address": "123 Test St",
                "locality": "Test City",
                "region": "Test Region",
                "postal-code": "12345"
            },
            region_id=1,
            url="http://testhotel.com",
            phone="1234567890",
            hotel_class=5.0,
            details={"description": "A great hotel"},
            type="Hotel",
            id=1
        )
        self.review = Review.objects.create(
            hotel=self.hotel,
            ratings={"overall": 4.5},
            title="Great Stay",
            text="Had a wonderful time at Test Hotel.",
            author={"username": "testuser"},
            date_stayed="2024-07-23",
            offering_id=1,
            num_helpful_votes=0,
            date=timezone.now(),
            via_mobile=False
        )
        self.overall_rating = HotelOverallRating.objects.create(
            hotel=self.hotel,
            offering_id=1,
            num_reviews=1,
            average_overall_rating=4.5
        )

    def test_home_view(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'hotelsapp/home.html')

    def test_hotels_view_logged_in(self):
        self.client.login(username='testuser', password='testpassword')
        response = self.client.get(reverse('hotels'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'hotelsapp/hotels.html')

    def test_hotels_view_not_logged_in(self):
        response = self.client.get(reverse('hotels'))
        self.assertRedirects(response, '/login/?next=/hotels/')

    def test_hotel_detail_view(self):
        self.client.login(username='testuser', password='testpassword')
        response = self.client.get(reverse('hotel_detail', kwargs={'hotel_id': self.hotel.id}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'hotelsapp/hotel_detail.html')

    def test_login_view(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'hotelsapp/login.html')
        
    def test_register_view(self):
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'hotelsapp/register.html')

    def test_logout_view(self):
        self.client.login(username='testuser', password='testpassword')
        response = self.client.get(reverse('logout'))
        self.assertRedirects(response, '/')
